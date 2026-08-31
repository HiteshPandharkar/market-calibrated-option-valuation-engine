"""Continuously compounded yield-curve abstractions."""

from abc import ABC, abstractmethod
from bisect import bisect_right
from dataclasses import dataclass
from math import exp

from pyoptionpricer.market._validation import require_finite_number
from pyoptionpricer.market.curves.conventions import (
    CompoundingConvention,
    DayCountConvention,
    InterpolationMethod,
)
from pyoptionpricer.market.exceptions import InvalidCurveError
from pyoptionpricer.market.observation import MarketObservation


def _validate_maturity(maturity: float) -> float:
    require_finite_number(maturity, "maturity", InvalidCurveError)
    maturity_value = float(maturity)
    if maturity_value < 0:
        raise InvalidCurveError("maturity must not be negative")
    return maturity_value


def _validate_rate(rate: float, field_name: str = "rate") -> float:
    require_finite_number(rate, field_name, InvalidCurveError)
    return float(rate)


class YieldCurve(ABC):
    """Term structure of continuously compounded annual zero rates.

    Maturities are Actual/365 Fixed year fractions from the valuation date.
    """

    compounding_convention = CompoundingConvention.CONTINUOUS
    day_count_convention = DayCountConvention.ACTUAL_365_FIXED

    @abstractmethod
    def zero_rate(self, maturity: float) -> float:
        """Return the annual continuously compounded rate at ``maturity``."""

    def discount_factor(self, maturity: float) -> float:
        """Return ``exp(-r(T) * T)`` under continuous compounding."""
        maturity_value = _validate_maturity(maturity)
        return exp(-self.zero_rate(maturity_value) * maturity_value)


@dataclass(frozen=True, slots=True)
class FlatYieldCurve(YieldCurve):
    """A yield curve with one zero rate at every maturity."""

    rate: float
    observation: MarketObservation[float] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "rate", _validate_rate(self.rate))

    @property
    def value(self) -> float:
        """Compatibility alias for the earlier flat-rate provider value."""
        return self.rate

    def zero_rate(self, maturity: float) -> float:
        _validate_maturity(maturity)
        return self.rate


@dataclass(frozen=True, slots=True)
class InterpolatedYieldCurve(YieldCurve):
    """Piecewise-linear zero curve with flat endpoint extrapolation."""

    maturities: tuple[float, ...]
    rates: tuple[float, ...]
    observations: tuple[MarketObservation[float], ...] = ()
    interpolation_method = InterpolationMethod.LINEAR_ZERO_RATE

    def __post_init__(self) -> None:
        if not self.maturities:
            raise InvalidCurveError("yield curve requires at least one pillar")
        if len(self.maturities) != len(self.rates):
            raise InvalidCurveError("maturities and rates must have equal lengths")
        if self.observations and len(self.observations) != len(self.rates):
            raise InvalidCurveError("observations must correspond to every pillar")

        maturities = tuple(_validate_maturity(item) for item in self.maturities)
        rates = tuple(
            _validate_rate(item, f"rates[{index}]")
            for index, item in enumerate(self.rates)
        )
        if any(left >= right for left, right in zip(maturities, maturities[1:])):
            raise InvalidCurveError("curve maturities must be strictly increasing")
        object.__setattr__(self, "maturities", maturities)
        object.__setattr__(self, "rates", rates)

    def zero_rate(self, maturity: float) -> float:
        maturity_value = _validate_maturity(maturity)
        if maturity_value <= self.maturities[0]:
            return self.rates[0]
        if maturity_value >= self.maturities[-1]:
            return self.rates[-1]

        right_index = bisect_right(self.maturities, maturity_value)
        left_index = right_index - 1
        left_maturity = self.maturities[left_index]
        right_maturity = self.maturities[right_index]
        weight = (maturity_value - left_maturity) / (
            right_maturity - left_maturity
        )
        return self.rates[left_index] + weight * (
            self.rates[right_index] - self.rates[left_index]
        )
