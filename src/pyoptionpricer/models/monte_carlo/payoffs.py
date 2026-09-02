"""Path-payoff evaluation boundaries."""

from typing import Protocol, runtime_checkable

from pyoptionpricer.domain import TerminalPayoff
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
