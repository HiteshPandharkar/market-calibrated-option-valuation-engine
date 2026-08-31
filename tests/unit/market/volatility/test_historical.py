from datetime import UTC, datetime, timedelta
from math import log, sqrt
from statistics import stdev

import pytest

from pyoptionpricer.market import (
    HistoricalBar,
    HistoricalVolatility,
    InvalidVolatilityInputError,
    MarketObservation,
    ReturnConvention,
    VolatilityModel,
)


START = datetime(2026, 1, 1, tzinfo=UTC)


def observations(prices: list[float]) -> list[MarketObservation[float]]:
    return [
        MarketObservation(price, START + timedelta(days=index), "TEST", "close")
        for index, price in enumerate(prices)
    ]


def bars(prices: list[float]) -> list[HistoricalBar]:
    return [
        HistoricalBar(
            START + timedelta(days=index),
            price,
            price,
            price,
            price,
            100.0,
            source="UPSTOX",
        )
        for index, price in enumerate(prices)
    ]


def test_historical_volatility_uses_annualized_sample_log_returns() -> None:
    prices = [100.0, 102.0, 101.0, 105.0]
    model = HistoricalVolatility(lookback=3, annualization_factor=252)
    expected_returns = [
        log(102.0 / 100.0),
        log(101.0 / 102.0),
        log(105.0 / 101.0),
    ]

    assert isinstance(model, VolatilityModel)
    assert model.return_convention is ReturnConvention.LOG
    assert model.estimate(observations(prices)) == pytest.approx(
        stdev(expected_returns) * sqrt(252)
    )


def test_historical_volatility_uses_only_latest_lookback_window() -> None:
    prices = [50.0, 100.0, 102.0, 101.0, 105.0]
    model = HistoricalVolatility(lookback=3, annualization_factor=1)

    assert model.estimate(observations(prices)) == pytest.approx(
        model.estimate(observations(prices[1:]))
    )


def test_historical_volatility_accepts_unsorted_canonical_upstox_bars() -> None:
    history = bars([100.0, 102.0, 101.0, 105.0])
    model = HistoricalVolatility(lookback=3, annualization_factor=252)

    assert model.estimate(reversed(history)) == pytest.approx(
        model.estimate(history)
    )


def test_historical_volatility_rejects_insufficient_history() -> None:
    with pytest.raises(InvalidVolatilityInputError, match="insufficient history"):
        HistoricalVolatility(lookback=3).estimate(observations([100.0, 101.0, 102.0]))


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"lookback": 1}, "lookback"),
        ({"lookback": True}, "lookback"),
        ({"annualization_factor": 0}, "annualization_factor"),
        ({"return_convention": "LOG"}, "return_convention"),
    ],
)
def test_historical_volatility_rejects_invalid_configuration(
    kwargs: dict[str, object], message: str
) -> None:
    with pytest.raises(InvalidVolatilityInputError, match=message):
        HistoricalVolatility(**kwargs)  # type: ignore[arg-type]


def test_volatility_rejects_duplicate_history_timestamps() -> None:
    history = observations([100.0, 101.0, 102.0])
    duplicate = MarketObservation(103.0, history[-1].timestamp, "TEST", "close")

    with pytest.raises(InvalidVolatilityInputError, match="unique"):
        HistoricalVolatility(lookback=2).estimate([*history, duplicate])

