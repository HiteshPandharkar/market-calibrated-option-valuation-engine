from datetime import UTC, datetime

import pytest

from pyoptionpricer.market import (
    ContinuousDividendYield,
    FlatYieldCurve,
    InvalidMarketSnapshotError,
    MarketObservation,
    MarketSnapshot,
    OptionQuote,
)


VALUATION_DATETIME = datetime(2026, 8, 28, 15, 30, tzinfo=UTC)
MARKET_TIMESTAMP = datetime(2026, 8, 28, 15, 29, tzinfo=UTC)


def make_spot(value: float = 1387.20) -> MarketObservation[float]:
    return MarketObservation(value, MARKET_TIMESTAMP, "UPSTOX", "last_price")


def make_quote() -> OptionQuote:
    return OptionQuote(100.0, 102.0, 101.0, MARKET_TIMESTAMP)


def test_snapshot_preserves_normalized_inputs() -> None:
    spot = make_spot()
    quote = make_quote()
    curve = FlatYieldCurve(0.065)
    dividends = ContinuousDividendYield(0.012)
    volatility = object()

    snapshot = MarketSnapshot(
        VALUATION_DATETIME,
        spot,
        quote,
        curve,
        dividends,
        volatility,
    )

    assert snapshot.valuation_datetime is VALUATION_DATETIME
    assert snapshot.spot is spot
    assert snapshot.option_quote is quote
    assert snapshot.yield_curve is curve
    assert snapshot.dividend_data is dividends
    assert snapshot.volatility_input is volatility


@pytest.mark.parametrize("value", [0.0, -1.0, float("nan"), float("inf")])
def test_snapshot_rejects_non_positive_or_non_finite_spot(value: float) -> None:
    with pytest.raises(InvalidMarketSnapshotError, match="spot.value"):
        MarketSnapshot(VALUATION_DATETIME, make_spot(value), make_quote())


def test_snapshot_requires_spot_provenance() -> None:
    with pytest.raises(InvalidMarketSnapshotError, match="MarketObservation"):
        MarketSnapshot(VALUATION_DATETIME, 1387.20, make_quote())  # type: ignore[arg-type]


def test_snapshot_rejects_naive_valuation_datetime() -> None:
    with pytest.raises(InvalidMarketSnapshotError, match="timezone-aware"):
        MarketSnapshot(
            datetime(2026, 8, 28, 15, 30),
            make_spot(),
            make_quote(),
        )


def test_snapshot_rejects_non_curve_rate_inputs() -> None:
    with pytest.raises(InvalidMarketSnapshotError, match="YieldCurve"):
        MarketSnapshot(
            VALUATION_DATETIME,
            make_spot(),
            make_quote(),
            yield_curve=0.05,  # type: ignore[arg-type]
        )
