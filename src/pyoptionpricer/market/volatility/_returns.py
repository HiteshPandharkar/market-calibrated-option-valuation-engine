"""Shared normalized-history handling for volatility estimators."""

from collections.abc import Iterable
from datetime import datetime
from math import isfinite, log

from pyoptionpricer.market.data.models import HistoricalBar
from pyoptionpricer.market.exceptions import InvalidVolatilityInputError
from pyoptionpricer.market.observation import MarketObservation
from pyoptionpricer.market.volatility.volatility_model import (
    PriceHistoryPoint,
    ReturnConvention,
)


def validate_configuration(
    lookback: int,
    annualization_factor: float,
    return_convention: ReturnConvention,
    *,
    minimum_lookback: int,
) -> None:
    if isinstance(lookback, bool) or not isinstance(lookback, int):
        raise InvalidVolatilityInputError("lookback must be an integer")
    if lookback < minimum_lookback:
        raise InvalidVolatilityInputError(
            f"lookback must be at least {minimum_lookback}"
        )
    if (
        isinstance(annualization_factor, bool)
        or not isinstance(annualization_factor, (int, float))
        or not isfinite(float(annualization_factor))
        or annualization_factor <= 0
    ):
        raise InvalidVolatilityInputError(
            "annualization_factor must be positive and finite"
        )
    if not isinstance(return_convention, ReturnConvention):
        raise InvalidVolatilityInputError(
            "return_convention must be a ReturnConvention"
        )


def log_returns(
    history: Iterable[PriceHistoryPoint], lookback: int
) -> tuple[float, ...]:
    try:
        points = tuple(history)
    except TypeError as error:
        raise InvalidVolatilityInputError("history must be iterable") from error

    required_prices = lookback + 1
    if len(points) < required_prices:
        raise InvalidVolatilityInputError(
            f"insufficient history: need at least {required_prices} prices "
            f"for {lookback} returns, received {len(points)}"
        )

    normalized = sorted(
        (_price_and_timestamp(point) for point in points),
        key=lambda item: item[1],
    )
    timestamps = [timestamp for _, timestamp in normalized]
    if len(set(timestamps)) != len(timestamps):
        raise InvalidVolatilityInputError("history timestamps must be unique")

    prices = [price for price, _ in normalized[-required_prices:]]
    return tuple(
        log(current / previous)
        for previous, current in zip(prices, prices[1:])
    )


def _price_and_timestamp(point: PriceHistoryPoint) -> tuple[float, datetime]:
    if isinstance(point, HistoricalBar):
        price = point.close
        timestamp = point.timestamp
    elif isinstance(point, MarketObservation):
        price = point.value
        timestamp = point.timestamp
    else:
        raise InvalidVolatilityInputError(
            "history must contain MarketObservation or HistoricalBar values"
        )

    if (
        isinstance(price, bool)
        or not isinstance(price, (int, float))
        or not isfinite(float(price))
        or price <= 0
    ):
        raise InvalidVolatilityInputError(
            "history prices must be positive and finite"
        )
    return float(price), timestamp
