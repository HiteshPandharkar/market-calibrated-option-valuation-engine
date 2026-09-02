"""Path-payoff evaluation boundaries and path-dependent product strategies."""

from statistics import fmean
from typing import Protocol, runtime_checkable

from pyoptionpricer.domain import OptionType, TerminalPayoff
from pyoptionpricer.models.monte_carlo.paths import GeneratedPath


@runtime_checkable
class PathPayoffEvaluator(Protocol):
    """Evaluate one generated path independently of the pricing engine."""

    def evaluate(self, path: GeneratedPath) -> float: ...


class TerminalPathPayoffEvaluator:
    """Adapt an engine-neutral terminal payoff to generated paths."""

    def __init__(self, payoff: TerminalPayoff) -> None:
        if not isinstance(payoff, TerminalPayoff):
            raise TypeError("payoff must implement TerminalPayoff")
        self._payoff = payoff

    def evaluate(self, path: GeneratedPath) -> float:
        if not isinstance(path, GeneratedPath):
            raise TypeError("path must be a GeneratedPath")
        return self._payoff.value_at(path.terminal_value)


class ArithmeticAveragePathPayoffEvaluator:
    """Evaluate a terminal payoff against selected arithmetic-average nodes."""

    def __init__(
        self, payoff: TerminalPayoff, observation_indices: tuple[int, ...]
    ) -> None:
        if not isinstance(payoff, TerminalPayoff):
            raise TypeError("payoff must implement TerminalPayoff")
        self._payoff = payoff
        self._observation_indices = _validate_indices(
            "observation_indices", observation_indices
        )

    def evaluate(self, path: GeneratedPath) -> float:
        observations = _selected_values(
            path, self._observation_indices, "observation_indices"
        )
        return self._payoff.value_at(fmean(observations))


class FixedStrikeLookbackPathPayoffEvaluator:
    """Evaluate a fixed-strike payoff against selected path extrema."""

    def __init__(
        self, payoff: TerminalPayoff, monitoring_indices: tuple[int, ...]
    ) -> None:
        if not isinstance(payoff, TerminalPayoff):
            raise TypeError("payoff must implement TerminalPayoff")
        self._payoff = payoff
        self._monitoring_indices = _validate_indices(
            "monitoring_indices", monitoring_indices
        )

    def evaluate(self, path: GeneratedPath) -> float:
        monitored = _selected_values(
            path, self._monitoring_indices, "monitoring_indices"
        )
        extremum = (
            max(monitored)
            if self._payoff.option_type is OptionType.CALL
            else min(monitored)
        )
        return self._payoff.value_at(extremum)


def _validate_indices(name: str, indices: tuple[int, ...]) -> tuple[int, ...]:
    try:
        normalized = tuple(indices)
    except TypeError as error:
        raise ValueError(f"{name} must be an iterable of node indices") from error
    if not normalized:
        raise ValueError(f"{name} must not be empty")
    if any(
        isinstance(item, bool) or not isinstance(item, int) or item < 0
        for item in normalized
    ):
        raise ValueError(f"{name} must contain only non-negative integers")
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{name} must not contain duplicates")
    return tuple(sorted(normalized))


def _selected_values(
    path: GeneratedPath, indices: tuple[int, ...], name: str
) -> tuple[float, ...]:
    if not isinstance(path, GeneratedPath):
        raise TypeError("path must be a GeneratedPath")
    if indices[-1] >= len(path.values):
        raise ValueError(f"{name} contains a node outside the generated path")
    return tuple(path.values[index] for index in indices)
