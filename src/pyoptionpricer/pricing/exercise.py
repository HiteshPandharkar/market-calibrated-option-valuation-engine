"""Exercise policies kept separate from generic tree mechanics."""

from typing import Protocol

from pyoptionpricer.domain import ExerciseStyle


class ExercisePolicy(Protocol):
    """Select a node value from continuation and intrinsic values."""

    def node_value(self, continuation: float, intrinsic: float) -> tuple[float, bool]:
        """Return the node value and whether early exercise was selected."""


class EuropeanExercisePolicy:
    def node_value(self, continuation: float, intrinsic: float) -> tuple[float, bool]:
        return continuation, False


class AmericanExercisePolicy:
    def node_value(self, continuation: float, intrinsic: float) -> tuple[float, bool]:
        if intrinsic > continuation:
            return intrinsic, True
        return continuation, False


def exercise_policy(style: ExerciseStyle) -> ExercisePolicy:
    """Return the policy for a validated option exercise style."""

    if style is ExerciseStyle.AMERICAN:
        return AmericanExercisePolicy()
    return EuropeanExercisePolicy()
