"""Immutable exchange-listed vanilla option contracts."""

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from math import isfinite


class OptionType(str, Enum):
    CALL = "CALL"
    PUT = "PUT"


class ExerciseStyle(str, Enum):
    EUROPEAN = "EUROPEAN"
    AMERICAN = "AMERICAN"


class AssetClass(str, Enum):
    EQUITY = "EQUITY"
    INDEX = "INDEX"


class Currency(str, Enum):
    INR = "INR"
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    JPY = "JPY"


class InvalidContractError(ValueError):
    """Raised when an option contract violates its domain invariants."""


@dataclass(frozen=True, slots=True)
class OptionContract:
    """Static terms of a plain-vanilla exchange option."""

    underlying: str
    strike: float
    expiry: date
    option_type: OptionType
    exercise_style: ExerciseStyle
    asset_class: AssetClass
    exchange: str | None = None
    contract_symbol: str | None = None
    currency: Currency = Currency.INR

    def __post_init__(self) -> None:
        if not isinstance(self.underlying, str) or not self.underlying.strip():
            raise InvalidContractError("underlying must be non-empty")
        if isinstance(self.strike, bool) or not isinstance(self.strike, (int, float)):
            raise InvalidContractError("strike must be a finite positive number")
        if not isfinite(self.strike) or self.strike <= 0:
            raise InvalidContractError("strike must be a finite positive number")
        if not isinstance(self.expiry, date) or isinstance(self.expiry, datetime):
            raise InvalidContractError("expiry must be a date")
        if not isinstance(self.option_type, OptionType):
            raise InvalidContractError("option_type must be an OptionType")
        if not isinstance(self.exercise_style, ExerciseStyle):
            raise InvalidContractError("exercise_style must be an ExerciseStyle")
        if not isinstance(self.asset_class, AssetClass):
            raise InvalidContractError("asset_class must be an AssetClass")
        if not isinstance(self.currency, Currency):
            raise InvalidContractError("currency must be a Currency")
        for name in ("exchange", "contract_symbol"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise InvalidContractError(f"{name} must be non-empty when supplied")

        object.__setattr__(self, "underlying", self.underlying.strip())
        object.__setattr__(self, "strike", float(self.strike))
