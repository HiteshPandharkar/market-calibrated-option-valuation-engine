from datetime import UTC, datetime
from pathlib import Path

import pytest

from pyoptionpricer.market import (
    ContinuousDividendYield,
    InterpolatedYieldCurve,
    MalformedMarketDataError,
    MarketDataUnavailableError,
    MarketObservation,
)
from pyoptionpricer.market.data import CSVMarketDataProvider, MarketDataProvider


FIXTURES = Path(__file__).parents[3] / "fixtures" / "market_data"
VALUATION_DATETIME = datetime(2026, 8, 28, 15, 30, tzinfo=UTC)
CONTRACT_ID = "ACME-20261231-1400-C"


@pytest.fixture
def provider() -> CSVMarketDataProvider:
    return CSVMarketDataProvider(FIXTURES)


def test_csv_provider_implements_provider_contract(
    provider: CSVMarketDataProvider,
) -> None:
    assert isinstance(provider, MarketDataProvider)


def test_point_in_time_queries_return_normalized_models(
    provider: CSVMarketDataProvider,
) -> None:
    spot = provider.get_spot("ACME", VALUATION_DATETIME)
    quote = provider.get_option_quote(CONTRACT_ID, VALUATION_DATETIME)

    assert spot.value == pytest.approx(1387.20)
    assert spot.source_vendor == "SAMPLE_EXCHANGE"
    assert spot.source_dataset == "SPOT_QUOTES"
    assert spot.source_field == "price"
    assert spot.timestamp == datetime(2026, 8, 28, 15, 29, tzinfo=UTC)
    assert quote.mid() == pytest.approx(35.35)


def test_price_history_is_inclusive_ordered_and_provenance_bearing(
    provider: CSVMarketDataProvider,
) -> None:
    history = provider.get_price_history(
        "ACME",
        datetime(2026, 8, 27, 0, tzinfo=UTC),
        VALUATION_DATETIME,
    )

    assert [observation.value for observation in history] == [1375.50, 1387.20]
    assert all(isinstance(item, MarketObservation) for item in history)
    assert history[0].source_dataset == "DAILY_CLOSES"


def test_complete_snapshot_is_built_offline_from_normalized_data(
    provider: CSVMarketDataProvider,
) -> None:
    snapshot = provider.build_snapshot(
        "ACME", CONTRACT_ID, "INR", VALUATION_DATETIME
    )

    assert snapshot.spot.value == pytest.approx(1387.20)
    assert snapshot.option_quote.mid() == pytest.approx(35.35)
    assert snapshot.yield_curve.value == pytest.approx(0.065)
    assert snapshot.dividend_data.value == pytest.approx(0.012)
    assert snapshot.volatility_input.value == pytest.approx(0.24)
    assert snapshot.yield_curve.zero_rate(0.75) == pytest.approx(0.065)
    assert snapshot.dividend_data.continuous_rate(0.75) == pytest.approx(0.012)
    assert isinstance(snapshot.dividend_data, ContinuousDividendYield)


def test_csv_provider_builds_interpolated_zero_curve(tmp_path: Path) -> None:
    (tmp_path / "yield_curves.csv").write_text(
        "currency,timestamp,maturity_years,rate,source,dataset,retrieved_at\n"
        "INR,2026-08-28T15:00:00+00:00,0.5,0.06,SAMPLE,ZERO_CURVE,\n"
        "INR,2026-08-28T15:00:00+00:00,1.0,0.07,SAMPLE,ZERO_CURVE,\n",
        encoding="utf-8",
    )
    curve = CSVMarketDataProvider(tmp_path).get_yield_curve(
        "INR", VALUATION_DATETIME
    )

    assert isinstance(curve, InterpolatedYieldCurve)
    assert curve.zero_rate(0.75) == pytest.approx(0.065)
    assert curve.observations[0].source_dataset == "ZERO_CURVE"


def test_missing_observation_has_actionable_context(
    provider: CSVMarketDataProvider,
) -> None:
    with pytest.raises(
        MarketDataUnavailableError, match=r"spots.csv: no data for symbol='MISSING'"
    ):
        provider.get_spot("MISSING", VALUATION_DATETIME)


def test_missing_required_column_is_reported(tmp_path: Path) -> None:
    (tmp_path / "spots.csv").write_text(
        "symbol,timestamp,source,dataset,retrieved_at\n"
        "ACME,2026-08-28T15:29:00+00:00,SAMPLE,SPOT,\n",
        encoding="utf-8",
    )
    provider = CSVMarketDataProvider(tmp_path)

    with pytest.raises(MalformedMarketDataError, match="missing required.*price"):
        provider.get_spot("ACME", VALUATION_DATETIME)


def test_malformed_value_reports_file_row_and_field(tmp_path: Path) -> None:
    (tmp_path / "spots.csv").write_text(
        "symbol,timestamp,price,source,dataset,retrieved_at\n"
        "ACME,2026-08-28T15:29:00+00:00,not-a-price,SAMPLE,SPOT,\n",
        encoding="utf-8",
    )
    provider = CSVMarketDataProvider(tmp_path)

    with pytest.raises(
        MalformedMarketDataError,
        match=r"spots.csv row 2: price must be a number",
    ):
        provider.get_spot("ACME", VALUATION_DATETIME)


@pytest.mark.parametrize("price", ["nan", "inf", "0", "-1"])
def test_invalid_spot_is_rejected_at_provider_boundary(
    tmp_path: Path, price: str
) -> None:
    (tmp_path / "spots.csv").write_text(
        "symbol,timestamp,price,source,dataset,retrieved_at\n"
        f"ACME,2026-08-28T15:29:00+00:00,{price},SAMPLE,SPOT,\n",
        encoding="utf-8",
    )
    provider = CSVMarketDataProvider(tmp_path)

    with pytest.raises(MalformedMarketDataError, match=r"spots.csv row 2"):
        provider.get_spot("ACME", VALUATION_DATETIME)


def test_duplicate_as_of_rows_are_rejected(tmp_path: Path) -> None:
    (tmp_path / "spots.csv").write_text(
        "symbol,timestamp,price,source,dataset,retrieved_at\n"
        "ACME,2026-08-28T15:29:00+00:00,1387.2,SAMPLE,SPOT,\n"
        "ACME,2026-08-28T15:29:00+00:00,1388.0,SAMPLE,SPOT,\n",
        encoding="utf-8",
    )
    provider = CSVMarketDataProvider(tmp_path)

    with pytest.raises(MalformedMarketDataError, match="duplicate rows"):
        provider.get_spot("ACME", VALUATION_DATETIME)
