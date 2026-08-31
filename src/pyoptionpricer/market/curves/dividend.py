"""Dividend-input abstractions for option cost of carry."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from math import exp

from pyoptionpricer.market._validation import require_finite_number
from pyoptionpricer.market.curves.conventions import (
    CompoundingConvention,
    DayCountConvention,
)
from pyoptionpricer.market.curves.yield_curve import _validate_maturity
from pyoptionpricer.market.exceptions import InvalidCurveError
from pyoptionpricer.market.observation import MarketObservation


class DividendYield(ABC):
    """Dividend input expressed as an annual continuous yield."""

    compounding_convention = CompoundingConvention.CONTINUOUS
    day_count_convention = DayCountConvention.ACTUAL_365_FIXED

    @abstractmethod
    def continuous_rate(self, maturity: float) -> float:
        """Return the annual continuous dividend yield at maturity."""

    def discount_factor(self, maturity: float) -> float:
        maturity_value = _validate_maturity(maturity)
        return exp(-self.continuous_rate(maturity_value) * maturity_value)


@dataclass(frozen=True, slots=True)
class ContinuousDividendYield(DividendYield):
    """A flat continuous dividend yield suitable for V1 CRR cost of carry."""

    rate: float
    observation: MarketObservation[float] | None = None

    def __post_init__(self) -> None:
        require_finite_number(self.rate, "rate", InvalidCurveError)
        if self.rate < 0:
            raise InvalidCurveError("dividend yield must not be negative")
        object.__setattr__(self, "rate", float(self.rate))

    @property
    def value(self) -> float:
        """Compatibility alias for the earlier provider observation value."""
        return self.rate

    def continuous_rate(self, maturity: float) -> float:
        _validate_maturity(maturity)
        return self.rate
