"""Project-owned terminal payoff definitions."""

from dataclasses import dataclass
from math import isfinite
from typing import Protocol, runtime_checkable

from pyoptionpricer.domain.option_contract import OptionType


class InvalidPayoffError(ValueError):
    """Raised when a payoff violates its domain invariants."""


@runtime_checkable
class TerminalPayoff(Protocol):
    """Value delivered by an option at a supplied underlying price."""

    option_type: OptionType
    strike: float

    def value_at(self, spot: float) -> float: ...


@dataclass(frozen=True, slots=True)
class VanillaPayoff:
    """Standard call or put terminal intrinsic value."""

    option_type: OptionType
    strike: float

    def __post_init__(self) -> None:
        _validate_terms(self.option_type, self.strike)
        object.__setattr__(self, "strike", float(self.strike))

    def value_at(self, spot: float) -> float:
        _validate_spot(spot)
        if self.option_type is OptionType.CALL:
            return max(spot - self.strike, 0.0)
        return max(self.strike - spot, 0.0)


@dataclass(frozen=True, slots=True)
class CashOrNothingPayoff:
    """Fixed cash payout when the terminal spot is strictly in the money.

    Both call and put pay zero at ``spot == strike``. This strict boundary is
    intentional and keeps the discontinuous terminal payoff unambiguous.
    """

    option_type: OptionType
    strike: float
    payout: float

    def __post_init__(self) -> None:
        _validate_terms(self.option_type, self.strike)
        _validate_positive_number("payout", self.payout)
        object.__setattr__(self, "strike", float(self.strike))
        object.__setattr__(self, "payout", float(self.payout))

    def value_at(self, spot: float) -> float:
        _validate_spot(spot)
        if self.option_type is OptionType.CALL:
            return self.payout if spot > self.strike else 0.0
        return self.payout if spot < self.strike else 0.0


def _validate_terms(option_type: OptionType, strike: float) -> None:
    if not isinstance(option_type, OptionType):
        raise InvalidPayoffError("option_type must be an OptionType")
    _validate_positive_number("strike", strike)


def _validate_positive_number(name: str, value: float) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not isfinite(value)
        or value <= 0
    ):
        raise InvalidPayoffError(f"{name} must be a finite positive number")


def _validate_spot(spot: float) -> None:
    if (
        isinstance(spot, bool)
        or not isinstance(spot, (int, float))
        or not isfinite(spot)
    ):
        raise InvalidPayoffError("spot must be finite")
