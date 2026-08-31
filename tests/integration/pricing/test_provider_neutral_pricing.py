from dataclasses import asdict
from datetime import UTC, date, datetime
import json
from pathlib import Path

import pytest

from pyoptionpricer import (
    AssetClass,
    CRRImpliedVolatilitySolver,
    CRRModelParameters,
    CRRPricingEngine,
    ExerciseStyle,
    OptionContract,
    OptionType,
    PricingRequest,
    compare_to_market,
)
from pyoptionpricer.market import (
    ContinuousDividendYield,
    FlatYieldCurve,
    MarketObservation,
    MarketSnapshot,
    OptionQuote,
)
from pyoptionpricer.market.data import CSVMarketDataProvider
from pyoptionpricer.market.data.providers.upstox.mapper import UpstoxMapper


FIXTURES = Path(__file__).parents[2] / "fixtures"


@pytest.mark.parametrize("source", ["CSV", "UPSTOX"])
def test_normalized_provider_snapshots_use_the_same_crr_workflow(source: str) -> None:
    valuation = datetime(2026, 8, 30, 12, 0, tzinfo=UTC)
    timestamp = datetime(2026, 8, 30, 11, 59, tzinfo=UTC)
    contract = OptionContract(
        "NIFTY",
        25000.0,
        date(2026, 11, 30),
        OptionType.CALL,
        ExerciseStyle.EUROPEAN,
        AssetClass.INDEX,
    )
    snapshot = MarketSnapshot(
        valuation,
        MarketObservation(24800.0, timestamp, source, "last_price"),
        OptionQuote(500.0, 510.0, 505.0, timestamp, source=source),
        FlatYieldCurve(0.065),
        ContinuousDividendYield(0.012),
        MarketObservation(0.18, timestamp, source, "volatility"),
    )

    result = CRRPricingEngine().price(
        PricingRequest(contract, snapshot, CRRModelParameters(200))
    )

    assert result.price == pytest.approx(956.8631533334566)
    assert result.inputs.spot.source == source
    assert result.inputs.volatility.source == source


def test_market_comparison_structure_is_provider_neutral() -> None:
    csv_quote = CSVMarketDataProvider(
        FIXTURES / "market_data"
    ).get_option_quote(
        "ACME-20261231-1400-C", datetime(2026, 8, 28, 15, 30, tzinfo=UTC)
    )
    with (FIXTURES / "upstox" / "full_market_quote.json").open(
        encoding="utf-8"
    ) as stream:
        payload = json.load(stream)
    upstox_quote = UpstoxMapper(
        lambda: datetime(2026, 8, 28, 10, 0, tzinfo=UTC)
    ).map_option_quote(payload, "NSE_FO|50001")

    csv_comparison = compare_to_market(36.0, csv_quote)
    upstox_comparison = compare_to_market(36.0, upstox_quote)

    assert upstox_quote.source_vendor == "UPSTOX"
    assert type(csv_comparison) is type(upstox_comparison)
    assert asdict(csv_comparison) == asdict(upstox_comparison)


def test_implied_volatility_accepts_csv_and_normalized_upstox_quotes() -> None:
    valuation = datetime(2026, 8, 28, 15, 30, tzinfo=UTC)
    csv_quote = CSVMarketDataProvider(FIXTURES / "market_data").get_option_quote(
        "ACME-20261231-1400-C", valuation
    )
    with (FIXTURES / "upstox" / "full_market_quote.json").open(
        encoding="utf-8"
    ) as stream:
        payload = json.load(stream)
    upstox_quote = UpstoxMapper(
        lambda: datetime(2026, 8, 28, 10, 0, tzinfo=UTC)
    ).map_option_quote(payload, "NSE_FO|50001")
    contract = OptionContract(
        "ACME",
        1400.0,
        date(2026, 12, 31),
        OptionType.CALL,
        ExerciseStyle.EUROPEAN,
        AssetClass.EQUITY,
    )

    def calibration_request(quote: OptionQuote) -> PricingRequest:
        snapshot = MarketSnapshot(
            valuation,
            MarketObservation(1387.2, valuation, quote.source or "CSV", "last_price"),
            quote,
            FlatYieldCurve(0.065),
            ContinuousDividendYield(0.012),
            0.20,
        )
        return PricingRequest(contract, snapshot, CRRModelParameters(200))

    solver = CRRImpliedVolatilitySolver()
    csv_result = solver.solve(calibration_request(csv_quote))
    upstox_result = solver.solve(calibration_request(upstox_quote))

    assert type(csv_result) is type(upstox_result)
    assert csv_result.implied_volatility == pytest.approx(
        upstox_result.implied_volatility
    )
    assert abs(upstox_result.pricing_residual) <= upstox_result.tolerance
