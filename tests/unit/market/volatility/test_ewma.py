from datetime import UTC, datetime, timedelta
from math import log, sqrt

import pytest

from pyoptionpricer.market import (
    EWMAVolatility,
    InvalidVolatilityInputError,
    MarketObservation,
)


START = datetime(2026, 1, 1, tzinfo=UTC)


def observations(prices: list[float]) -> list[MarketObservation[float]]:
    return [
        MarketObservation(price, START + timedelta(days=index), "TEST", "close")
        for index, price in enumerate(prices)
    ]


def test_ewma_volatility_uses_recursive_variance_and_annualizes() -> None:
    prices = [100.0, 103.0, 101.0, 106.0]
    decay = 0.8
    returns = [
        log(103.0 / 100.0),
        log(101.0 / 103.0),
        log(106.0 / 101.0),
    ]
    expected_variance = returns[0] ** 2
    for value in returns[1:]:
        expected_variance = decay * expected_variance + (1 - decay) * value**2

    result = EWMAVolatility(
        lookback=3, decay=decay, annualization_factor=252
    ).estimate(observations(prices))

    assert result == pytest.approx(sqrt(expected_variance * 252))


def test_ewma_decay_is_configurable() -> None:
    history = observations([100.0, 110.0, 109.0])

    slow = EWMAVolatility(lookback=2, decay=0.95, annualization_factor=1)
    fast = EWMAVolatility(lookback=2, decay=0.20, annualization_factor=1)

    assert slow.estimate(history) > fast.estimate(history)


def test_ewma_rejects_insufficient_history() -> None:
    with pytest.raises(InvalidVolatilityInputError, match="insufficient history"):
        EWMAVolatility(lookback=2).estimate(observations([100.0, 101.0]))


@pytest.mark.parametrize("decay", [0, 1, -0.1, 1.1, float("nan"), True])
def test_ewma_rejects_invalid_decay(decay: float) -> None:
    with pytest.raises(InvalidVolatilityInputError, match="decay"):
        EWMAVolatility(decay=decay)

