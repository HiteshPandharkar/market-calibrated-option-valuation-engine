"""Convergence analysis for provider-neutral CRR pricing requests."""

from dataclasses import dataclass, replace
from math import isfinite

from pyoptionpricer.models.tree import CRRModelParameters, InvalidTreeParametersError
from pyoptionpricer.pricing.diagnostics import (
    DiagnosticCheck,
    DiagnosticCode,
    DiagnosticStatus,
)
from pyoptionpricer.pricing.requests import PricingRequest
from pyoptionpricer.pricing.results import PricingResult
from pyoptionpricer.models.tree.pricing_engine import CRRPricingEngine
from pyoptionpricer.pricing.errors import PricingError


@dataclass(frozen=True, slots=True)
class ConvergenceConfig:
    """Step schedule and stability criterion for one convergence run."""

    step_counts: tuple[int, ...] = (10, 25, 50, 100, 250, 500, 1000)
    tolerance: float = 0.01
    stability_window: int = 3

    def __post_init__(self) -> None:
        if len(self.step_counts) < 2:
            raise ValueError("step_counts must contain at least two values")
        if any(
            isinstance(steps, bool) or not isinstance(steps, int) or steps < 2
            for steps in self.step_counts
        ):
            raise ValueError("every step count must be an integer of at least two")
        if tuple(sorted(set(self.step_counts))) != self.step_counts:
            raise ValueError("step_counts must be unique and strictly increasing")
        if not isfinite(self.tolerance) or self.tolerance <= 0:
            raise ValueError("tolerance must be finite and positive")
        if not 2 <= self.stability_window <= len(self.step_counts):
            raise ValueError("stability_window must be between two and the run size")


@dataclass(frozen=True, slots=True)
class ConvergencePoint:
    """Stored outcome for one requested tree resolution."""

    steps: int
    pricing_result: PricingResult | None
    error: str | None = None

    @property
    def price(self) -> float | None:
        return None if self.pricing_result is None else self.pricing_result.price


@dataclass(frozen=True, slots=True)
class ConvergenceResult:
    """All run outcomes and their aggregate stability diagnostic."""

    points: tuple[ConvergencePoint, ...]
    tolerance: float
    stability_window: int
    diagnostic: DiagnosticCheck

    @property
    def converged(self) -> bool:
        return self.diagnostic.status is DiagnosticStatus.PASS


class CRRConvergenceRunner:
    """Evaluate a pricing request over an explicit CRR step schedule."""

    def __init__(self, engine: CRRPricingEngine | None = None) -> None:
        self._engine = engine or CRRPricingEngine()

    def run(
        self,
        request: PricingRequest,
        config: ConvergenceConfig = ConvergenceConfig(),
    ) -> ConvergenceResult:
        if not isinstance(request, PricingRequest):
            raise TypeError("request must be a PricingRequest")
        if not isinstance(config, ConvergenceConfig):
            raise TypeError("config must be a ConvergenceConfig")

        points: list[ConvergencePoint] = []
        for steps in config.step_counts:
            candidate = replace(
                request, model_parameters=CRRModelParameters(steps=steps)
            )
            try:
                result = self._engine.price(candidate)
            except (InvalidTreeParametersError, PricingError) as error:
                points.append(ConvergencePoint(steps, None, str(error)))
            else:
                points.append(ConvergencePoint(steps, result))

        failures = [point for point in points if point.error is not None]
        if failures:
            diagnostic = DiagnosticCheck(
                DiagnosticCode.TREE_CONVERGENCE,
                DiagnosticStatus.FAIL,
                f"{len(failures)} of {len(points)} convergence prices failed",
            )
        else:
            tail = points[-config.stability_window :]
            prices = [
                point.pricing_result.price
                for point in tail
                if point.pricing_result is not None
            ]
            assert len(prices) == config.stability_window
            spread = max(prices) - min(prices)
            if spread <= config.tolerance:
                status = DiagnosticStatus.PASS
                message = (
                    f"final {config.stability_window} prices are stable within "
                    f"{config.tolerance:g}"
                )
            else:
                status = DiagnosticStatus.WARN
                message = (
                    f"final {config.stability_window} price spread {spread:g} exceeds "
                    f"tolerance {config.tolerance:g}"
                )
            diagnostic = DiagnosticCheck(
                DiagnosticCode.TREE_CONVERGENCE, status, message
            )

        return ConvergenceResult(
            tuple(points), config.tolerance, config.stability_window, diagnostic
        )
