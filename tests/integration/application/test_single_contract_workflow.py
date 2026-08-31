from datetime import UTC, date, datetime, timedelta
import json
from math import exp, sqrt
from pathlib import Path
from typing import Any

import pytest

from pyoptionpricer import (
    AssetClass,
    CRRModelParameters,
    ContractSelection,
    DiagnosticStatus,
    ExerciseStyle,
    MarketDataSynchronizationError,
    OptionContract,
    OptionType,
    SingleContractValuationRequest,
    SingleContractValuationService,
    VolatilitySelection,
    VolatilitySource,
)
from pyoptionpricer.market import (
    ContinuousDividendYield,
    FlatYieldCurve,
    MarketDataUnavailableError,
    MarketObservation,
)
from pyoptionpricer.market.data import CSVMarketDataProvider
from pyoptionpricer.market.data.providers.upstox import UpstoxMarketDataProvider


FIXTURES = Path(__file__).parents[2] / "fixtures"
VALUATION_TIME = datetime(2026, 8, 28, 15, 30, tzinfo=UTC)
UPSTOX_TIME = datetime(2026, 8, 28, 10, 0, tzinfo=UTC)
UNDERLYING_ID = "EQUITY_CASH:NSE:RELIANCE"
OPTION_ID = "EQUITY_DERIVATIVES:NSE:RELIANCE 29 SEP 26 1400 CE"


class FixtureUpstoxClient:
    def _load(self, filename: str) -> Any:
        with (FIXTURES / "upstox" / filename).open(encoding="utf-8") as stream:
            return json.load(stream)

    def fetch_instruments(self) -> list[dict[str, Any]]:
        return self._load("instruments.json")

    def fetch_full_quote(self, vendor_instrument_id: str) -> dict[str, Any]:
        return self._load("full_market_quote.json")

    def fetch_historical_candles(
        self, vendor_instrument_id: str, from_date: str, to_date: str
    ) -> dict[str, Any]:
        return self._load("historical_candles_60.json")

    def fetch_option_chain(
        self, vendor_underlying_id: str, expiry_date: str
    ) -> dict[str, Any]:
        return self._load("option_chain.json")


def test_csv_files_reproduce_complete_single_contract_valuation() -> None:
    provider = CSVMarketDataProvider(FIXTURES / "market_data")
    contract = OptionContract(
        underlying="ACME",
        strike=1400.0,
        expiry=date(2026, 12, 31),
        option_type=OptionType.CALL,
        exercise_style=ExerciseStyle.EUROPEAN,
        asset_class=AssetClass.EQUITY,
        exchange="SAMPLE_EXCHANGE",
        contract_symbol="ACME-20261231-1400-C",
    )

    valuation = SingleContractValuationService(provider).value(
        SingleContractValuationRequest(
            selection=ContractSelection(
                "ACME", "ACME-20261231-1400-C", contract=contract
            ),
            valuation_datetime=VALUATION_TIME,
            model_parameters=CRRModelParameters(200),
        )
    )

    assert valuation.contract is contract
    assert valuation.pricing_result.price == pytest.approx(83.41348229842129)
    assert valuation.pricing_result.greeks.delta > 0
    assert valuation.market_comparison.market_mid == pytest.approx(35.35)
    assert valuation.diagnostics.overall_status is DiagnosticStatus.PASS
    assert valuation.pricing_result.inputs.spot.source == "SAMPLE_EXCHANGE"
    assert valuation.pricing_result.inputs.volatility.source == "SAMPLE_MODEL"


def test_upstox_fixture_path_uses_same_service_and_retains_provenance() -> None:
    provider = UpstoxMarketDataProvider(
        FixtureUpstoxClient(), clock=lambda: UPSTOX_TIME
    )
    rate_observation = MarketObservation(
        0.065, UPSTOX_TIME, "VALUATION_ASSUMPTION", "continuous_zero_rate"
    )
    dividend_observation = MarketObservation(
        0.012, UPSTOX_TIME, "VALUATION_ASSUMPTION", "continuous_dividend_yield"
    )

    valuation = SingleContractValuationService(provider).value(
        SingleContractValuationRequest(
            selection=ContractSelection(UNDERLYING_ID, OPTION_ID),
            valuation_datetime=UPSTOX_TIME,
            model_parameters=CRRModelParameters(200),
            volatility=VolatilitySelection(
                source=VolatilitySource.EWMA, lookback=60
            ),
            yield_curve=FlatYieldCurve(0.065, rate_observation),
            dividend_data=ContinuousDividendYield(0.012, dividend_observation),
        )
    )

    assert valuation.contract.strike == 1400.0
    assert valuation.contract.contract_symbol == "RELIANCE 29 SEP 26 1400 CE"
    assert valuation.contract.expiry == date(2026, 9, 29)
    assert valuation.instrument_reference is not None
    assert valuation.instrument_reference.vendor == "UPSTOX"
    assert valuation.market_snapshot.option_quote.source == "UPSTOX"
    assert valuation.pricing_result.inputs.spot.source == "UPSTOX"
    assert valuation.pricing_result.inputs.volatility.source == "UPSTOX"
    assert valuation.pricing_result.inputs.strike.source == (
        "UPSTOX:INSTRUMENT_REFERENCE"
    )
    assert valuation.pricing_result.inputs.maturity.source == (
        "UPSTOX:INSTRUMENT_REFERENCE+market_snapshot"
    )
    assert valuation.pricing_result.inputs.volatility.field == (
        "ewma_annualized_volatility"
    )
    assert valuation.pricing_result.inputs.risk_free_rate.source == (
        "VALUATION_ASSUMPTION"
    )
    assert valuation.market_comparison.market_mid == pytest.approx(35.35)
    assert valuation.diagnostics.overall_status is DiagnosticStatus.PASS
    assert valuation.implied_volatility.market_midpoint == pytest.approx(35.35)
    assert valuation.implied_volatility.model_price == pytest.approx(
        35.35, abs=1e-6
    )
    assert type(valuation.pricing_result).__module__.startswith("pyoptionpricer.pricing")


def test_upstox_market_iv_surface_drives_crr_pricing_by_default() -> None:
    provider = UpstoxMarketDataProvider(
        FixtureUpstoxClient(), clock=lambda: UPSTOX_TIME
    )
    valuation = SingleContractValuationService(provider).value(
        SingleContractValuationRequest(
            selection=ContractSelection(UNDERLYING_ID, OPTION_ID),
            valuation_datetime=UPSTOX_TIME,
            model_parameters=CRRModelParameters(200),
            yield_curve=FlatYieldCurve(0.065),
            dividend_data=ContinuousDividendYield(0.012),
        )
    )

    assert valuation.volatility_surface is not None
    assert len(valuation.volatility_surface.points) == 1
    assert valuation.used_volatility_fallback is False
    assert valuation.pricing_result.inputs.volatility.value == pytest.approx(0.225)
    assert valuation.pricing_result.inputs.volatility.field == (
        "market_implied_volatility"
    )
    assert valuation.pricing_result.inputs.volatility.method == (
        "market IV surface selection"
    )
    assert valuation.market_snapshot.option_quote.dataset == "OPTION_CHAIN"
    expected_up_factor = exp(
        0.225 * sqrt(valuation.pricing_result.inputs.maturity.value / 200)
    )
    assert (
        valuation.pricing_result.diagnostics.tree_parameters.up_factor
        == pytest.approx(expected_up_factor)
    )
    assert valuation.pricing_result.greeks.delta > 0
    assert valuation.market_comparison.market_bid == pytest.approx(35.1)
    assert valuation.market_comparison.market_ask == pytest.approx(35.6)
    assert valuation.market_comparison.market_mid == pytest.approx(35.35)


class UnreliableIVUpstoxClient(FixtureUpstoxClient):
    def fetch_option_chain(
        self, vendor_underlying_id: str, expiry_date: str
    ) -> dict[str, Any]:
        payload = self._load("option_chain.json")
        payload["data"][0]["call_options"]["option_greeks"]["iv"] = 0.0
        return payload


def test_history_is_used_only_when_market_iv_fallback_is_configured() -> None:
    provider = UpstoxMarketDataProvider(
        UnreliableIVUpstoxClient(), clock=lambda: UPSTOX_TIME
    )
    common = dict(
        selection=ContractSelection(UNDERLYING_ID, OPTION_ID),
        valuation_datetime=UPSTOX_TIME,
        model_parameters=CRRModelParameters(200),
        yield_curve=FlatYieldCurve(0.0),
        dividend_data=ContinuousDividendYield(0.0),
    )

    with pytest.raises(MarketDataUnavailableError, match="reliable"):
        SingleContractValuationService(provider).value(
            SingleContractValuationRequest(**common)
        )

    valuation = SingleContractValuationService(provider).value(
        SingleContractValuationRequest(
            **common,
            volatility=VolatilitySelection(
                fallback_source=VolatilitySource.HISTORICAL,
                lookback=60,
            ),
        )
    )

    assert valuation.used_volatility_fallback is True
    assert valuation.volatility_surface is None
    assert valuation.pricing_result.inputs.volatility.field == (
        "historical_annualized_volatility"
    )


def test_workflow_rejects_stale_or_unsynchronized_quotes() -> None:
    provider = UpstoxMarketDataProvider(
        FixtureUpstoxClient(), clock=lambda: UPSTOX_TIME
    )

    with pytest.raises(
        MarketDataSynchronizationError, match="underlying quote is stale"
    ):
        SingleContractValuationService(provider).value(
            SingleContractValuationRequest(
                selection=ContractSelection(UNDERLYING_ID, OPTION_ID),
                valuation_datetime=UPSTOX_TIME,
                yield_curve=FlatYieldCurve(0.065),
                dividend_data=ContinuousDividendYield(0.012),
                maximum_market_age=timedelta(seconds=30),
            )
        )
