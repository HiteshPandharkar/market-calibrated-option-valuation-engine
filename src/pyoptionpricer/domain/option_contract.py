"""Immutable option instruments and product-specific contracts."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from math import isfinite
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyoptionpricer.domain.payoffs import TerminalPayoff


class OptionType(str, Enum):
    CALL = "CALL"
    PUT = "PUT"


class ExerciseStyle(str, Enum):
    EUROPEAN = "EUROPEAN"
    AMERICAN = "AMERICAN"
    BERMUDAN = "BERMUDAN"


class AssetClass(str, Enum):
    EQUITY = "EQUITY"
    INDEX = "INDEX"


class OptionProduct(str, Enum):
    """Canonical option product families used for model capability checks."""

    VANILLA = "VANILLA"
    DIGITAL = "DIGITAL"
    BARRIER = "BARRIER"
    ASIAN = "ASIAN"
    LOOKBACK = "LOOKBACK"


class Currency(str, Enum):
    INR = "INR"
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    JPY = "JPY"


class InvalidContractError(ValueError):
    """Raised when an option contract violates its domain invariants."""


@dataclass(frozen=True, slots=True)
class BermudanExercise:
    """Contractual dates on which a Bermudan option may be exercised."""

    exercise_dates: tuple[date, ...]

    def __post_init__(self) -> None:
        try:
            dates = tuple(self.exercise_dates)
        except TypeError as error:
            raise InvalidContractError(
                "exercise_dates must be an iterable of dates"
            ) from error
        if not dates:
            raise InvalidContractError("exercise_dates must not be empty")
        if any(
            not isinstance(item, date) or isinstance(item, datetime)
            for item in dates
        ):
            raise InvalidContractError("exercise_dates must contain only dates")
        if len(set(dates)) != len(dates):
            raise InvalidContractError("exercise_dates must not contain duplicates")
        object.__setattr__(self, "exercise_dates", tuple(sorted(dates)))


@dataclass(frozen=True, slots=True)
class OptionContract(ABC):
    """Common static terms shared by supported option products."""

    underlying: str
    strike: float
    expiry: date
    option_type: OptionType
    exercise_style: ExerciseStyle
    asset_class: AssetClass
    exchange: str | None = None
    contract_symbol: str | None = None
    currency: Currency = Currency.INR
    exercise_schedule: BermudanExercise | None = None

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
        if self.exercise_style is ExerciseStyle.BERMUDAN:
            if not isinstance(self.exercise_schedule, BermudanExercise):
                raise InvalidContractError(
                    "Bermudan contracts require a BermudanExercise exercise_schedule"
                )
            if self.expiry not in self.exercise_schedule.exercise_dates:
                raise InvalidContractError(
                    "Bermudan exercise_schedule must include expiry explicitly"
                )
            if any(item > self.expiry for item in self.exercise_schedule.exercise_dates):
                raise InvalidContractError(
                    "Bermudan exercise dates must not occur after expiry"
                )
        elif self.exercise_schedule is not None:
            raise InvalidContractError(
                "exercise_schedule is only valid for Bermudan contracts"
            )
        for name in ("exchange", "contract_symbol"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise InvalidContractError(f"{name} must be non-empty when supplied")

        object.__setattr__(self, "underlying", self.underlying.strip())
        object.__setattr__(self, "strike", float(self.strike))

    @property
    @abstractmethod
    def product(self) -> OptionProduct:
        """Identify the product family for engine capability validation."""
        raise NotImplementedError

    @property
    @abstractmethod
    def payoff(self) -> "TerminalPayoff":
        """Return the product's engine-neutral terminal payoff."""
        raise NotImplementedError


class VanillaOptionContract(OptionContract):
    """Static terms of a plain-vanilla exchange option."""

    @property
    def product(self) -> OptionProduct:
        """Identify this contract as a plain-vanilla option."""
        return OptionProduct.VANILLA

    @property
    def payoff(self) -> "TerminalPayoff":
        """Return the contract's engine-neutral terminal payoff."""
        from pyoptionpricer.domain.payoffs import VanillaPayoff

        return VanillaPayoff(self.option_type, self.strike)


@dataclass(frozen=True, slots=True, kw_only=True)
class DigitalOptionContract(OptionContract):
    """Cash-or-nothing option terms with a configurable fixed payout."""

    cash_payout: float

    def __post_init__(self) -> None:
        OptionContract.__post_init__(self)
        if (
            isinstance(self.cash_payout, bool)
            or not isinstance(self.cash_payout, (int, float))
            or not isfinite(self.cash_payout)
            or self.cash_payout <= 0
        ):
            raise InvalidContractError(
                "cash_payout must be a finite positive number"
            )
        object.__setattr__(self, "cash_payout", float(self.cash_payout))

    @property
    def product(self) -> OptionProduct:
        return OptionProduct.DIGITAL

    @property
    def payoff(self) -> "TerminalPayoff":
        from pyoptionpricer.domain.payoffs import CashOrNothingPayoff

        return CashOrNothingPayoff(
            self.option_type, self.strike, self.cash_payout
        )
