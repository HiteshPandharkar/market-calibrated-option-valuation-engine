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


class BarrierDirection(str, Enum):
    """Direction in which a monitored level activates a barrier."""

    UP = "UP"
    DOWN = "DOWN"


class BarrierKnockType(str, Enum):
    """Whether touching the barrier activates or terminates the option."""

    IN = "IN"
    OUT = "OUT"


class BarrierMonitoringConvention(str, Enum):
    """Supported observation schedules for a barrier contract."""

    DISCRETE_NODES = "DISCRETE_NODES"


class AveragingMethod(str, Enum):
    """Supported methods for reducing Asian option observations."""

    ARITHMETIC = "ARITHMETIC"


class PathMonitoringConvention(str, Enum):
    """Supported monitoring conventions for path-dependent contracts."""

    DISCRETE_DATES = "DISCRETE_DATES"


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


@dataclass(frozen=True, slots=True, kw_only=True)
class BarrierOptionContract(OptionContract):
    """Single-barrier terms over a European vanilla terminal payoff.

    The rebate is paid when a knock-out barrier is first observed. For a
    knock-in option it is paid at expiry only when the barrier was never
    observed. Monitoring includes the valuation node and every CRR time node.
    """

    barrier_level: float
    barrier_direction: BarrierDirection
    knock_type: BarrierKnockType
    rebate: float = 0.0
    monitoring_convention: BarrierMonitoringConvention = (
        BarrierMonitoringConvention.DISCRETE_NODES
    )

    def __post_init__(self) -> None:
        OptionContract.__post_init__(self)
        if self.exercise_style is not ExerciseStyle.EUROPEAN:
            raise InvalidContractError(
                "barrier options currently support only European exercise"
            )
        if (
            isinstance(self.barrier_level, bool)
            or not isinstance(self.barrier_level, (int, float))
            or not isfinite(self.barrier_level)
            or self.barrier_level <= 0
        ):
            raise InvalidContractError(
                "barrier_level must be a finite positive number"
            )
        if not isinstance(self.barrier_direction, BarrierDirection):
            raise InvalidContractError(
                "barrier_direction must be a BarrierDirection"
            )
        if not isinstance(self.knock_type, BarrierKnockType):
            raise InvalidContractError("knock_type must be a BarrierKnockType")
        if (
            isinstance(self.rebate, bool)
            or not isinstance(self.rebate, (int, float))
            or not isfinite(self.rebate)
            or self.rebate < 0
        ):
            raise InvalidContractError("rebate must be a finite non-negative number")
        if not isinstance(
            self.monitoring_convention, BarrierMonitoringConvention
        ):
            raise InvalidContractError(
                "monitoring_convention must be a BarrierMonitoringConvention"
            )
        object.__setattr__(self, "barrier_level", float(self.barrier_level))
        object.__setattr__(self, "rebate", float(self.rebate))

    @property
    def product(self) -> OptionProduct:
        return OptionProduct.BARRIER

    @property
    def payoff(self) -> "TerminalPayoff":
        from pyoptionpricer.domain.payoffs import VanillaPayoff

        return VanillaPayoff(self.option_type, self.strike)


def _normalize_monitoring_schedule(
    name: str, schedule: tuple[date, ...], expiry: date
) -> tuple[date, ...]:
    try:
        dates = tuple(schedule)
    except TypeError as error:
        raise InvalidContractError(f"{name} must be an iterable of dates") from error
    if not dates:
        raise InvalidContractError(f"{name} must not be empty")
    if any(
        not isinstance(item, date) or isinstance(item, datetime) for item in dates
    ):
        raise InvalidContractError(f"{name} must contain only dates")
    if len(set(dates)) != len(dates):
        raise InvalidContractError(f"{name} must not contain duplicates")
    if any(item > expiry for item in dates):
        raise InvalidContractError(f"{name} must not contain dates after expiry")
    return tuple(sorted(dates))


@dataclass(frozen=True, slots=True, kw_only=True)
class AsianOptionContract(OptionContract):
    """Arithmetic-average price option with explicit discrete observations."""

    observation_schedule: tuple[date, ...]
    averaging_method: AveragingMethod = AveragingMethod.ARITHMETIC
    monitoring_convention: PathMonitoringConvention = (
        PathMonitoringConvention.DISCRETE_DATES
    )

    def __post_init__(self) -> None:
        OptionContract.__post_init__(self)
        if self.exercise_style is not ExerciseStyle.EUROPEAN:
            raise InvalidContractError(
                "Asian options currently support only European exercise"
            )
        if not isinstance(self.averaging_method, AveragingMethod):
            raise InvalidContractError("averaging_method must be an AveragingMethod")
        if not isinstance(self.monitoring_convention, PathMonitoringConvention):
            raise InvalidContractError(
                "monitoring_convention must be a PathMonitoringConvention"
            )
        object.__setattr__(
            self,
            "observation_schedule",
            _normalize_monitoring_schedule(
                "observation_schedule", self.observation_schedule, self.expiry
            ),
        )

    @property
    def product(self) -> OptionProduct:
        return OptionProduct.ASIAN

    @property
    def payoff(self) -> "TerminalPayoff":
        from pyoptionpricer.domain.payoffs import VanillaPayoff

        return VanillaPayoff(self.option_type, self.strike)


@dataclass(frozen=True, slots=True, kw_only=True)
class LookbackOptionContract(OptionContract):
    """Fixed-strike lookback option with explicit discrete monitoring."""

    monitoring_schedule: tuple[date, ...]
    monitoring_convention: PathMonitoringConvention = (
        PathMonitoringConvention.DISCRETE_DATES
    )

    def __post_init__(self) -> None:
        OptionContract.__post_init__(self)
        if self.exercise_style is not ExerciseStyle.EUROPEAN:
            raise InvalidContractError(
                "lookback options currently support only European exercise"
            )
        if not isinstance(self.monitoring_convention, PathMonitoringConvention):
            raise InvalidContractError(
                "monitoring_convention must be a PathMonitoringConvention"
            )
        object.__setattr__(
            self,
            "monitoring_schedule",
            _normalize_monitoring_schedule(
                "monitoring_schedule", self.monitoring_schedule, self.expiry
            ),
        )

    @property
    def product(self) -> OptionProduct:
        return OptionProduct.LOOKBACK

    @property
    def payoff(self) -> "TerminalPayoff":
        from pyoptionpricer.domain.payoffs import VanillaPayoff

        return VanillaPayoff(self.option_type, self.strike)
