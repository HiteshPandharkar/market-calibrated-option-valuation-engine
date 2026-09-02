"""Exercise policies and contractual-date mapping for lattice engines."""

from datetime import date
from typing import Protocol

from pyoptionpricer.domain import BermudanExercise, ExerciseStyle


class ExerciseScheduleMappingError(ValueError):
    """Raised when contractual exercise dates cannot map to a tree grid."""


class ExercisePolicy(Protocol):
    """Select a node value from continuation and intrinsic values."""

    def node_value(
        self, continuation: float, intrinsic: float, time_index: int | None = None
    ) -> tuple[float, bool]:
        """Return the node value and whether early exercise was selected."""


class EuropeanExercisePolicy:
    def node_value(
        self, continuation: float, intrinsic: float, time_index: int | None = None
    ) -> tuple[float, bool]:
        return continuation, False


class AmericanExercisePolicy:
    def node_value(
        self, continuation: float, intrinsic: float, time_index: int | None = None
    ) -> tuple[float, bool]:
        if intrinsic > continuation:
            return intrinsic, True
        return continuation, False


class BermudanExercisePolicy:
    """Permit early exercise only at explicitly mapped tree steps."""

    def __init__(self, exercise_steps: frozenset[int]) -> None:
        self.exercise_steps = exercise_steps

    def node_value(
        self, continuation: float, intrinsic: float, time_index: int | None = None
    ) -> tuple[float, bool]:
        if time_index in self.exercise_steps and intrinsic > continuation:
            return intrinsic, True
        return continuation, False


def map_bermudan_exercise_steps(
    schedule: BermudanExercise,
    valuation_date: date,
    expiry: date,
    steps: int,
) -> frozenset[int]:
    """Map active contractual dates to exactly aligned Actual/365 tree steps.

    Dates before valuation are already lapsed and are ignored. The valuation
    date maps to step zero and expiry maps to the terminal step. No nearest-step
    or tolerance-based adjustment is performed.
    """

    maturity_days = (expiry - valuation_date).days
    if maturity_days <= 0:
        raise ExerciseScheduleMappingError("expiry must be after valuation_date")
    mapped_steps: set[int] = set()
    for exercise_date in schedule.exercise_dates:
        offset_days = (exercise_date - valuation_date).days
        if offset_days < 0:
            continue
        scaled_offset = offset_days * steps
        if scaled_offset % maturity_days:
            raise ExerciseScheduleMappingError(
                f"exercise date {exercise_date.isoformat()} does not align exactly "
                f"with the {steps}-step CRR grid"
            )
        mapped_steps.add(scaled_offset // maturity_days)
    return frozenset(mapped_steps)


def exercise_policy(
    style: ExerciseStyle,
    bermudan_steps: frozenset[int] = frozenset(),
) -> ExercisePolicy:
    """Return the policy for a validated option exercise style."""

    if style is ExerciseStyle.AMERICAN:
        return AmericanExercisePolicy()
    if style is ExerciseStyle.BERMUDAN:
        return BermudanExercisePolicy(bermudan_steps)
    return EuropeanExercisePolicy()
