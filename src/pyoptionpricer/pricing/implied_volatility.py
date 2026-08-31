"""Provider-neutral implied-volatility calibration with the CRR engine."""

from dataclasses import dataclass, replace
from math import isfinite

from pyoptionpricer.models.tree import InvalidTreeParametersError
from pyoptionpricer.pricing.requests import PricingRequest
from pyoptionpricer.pricing.results import PricingResult
from pyoptionpricer.pricing.tree_engine import CRRPricingEngine, PricingError


class ImpliedVolatilityError(RuntimeError):
    """Raised when an implied volatility cannot be calibrated."""


class ImpliedVolatilityConvergenceError(ImpliedVolatilityError):
    """Raised when a bracketed calibration exceeds its iteration budget."""

    def __init__(self, iterations: int, pricing_residual: float) -> None:
        self.iterations = iterations
        self.pricing_residual = pricing_residual
        super().__init__(
            "implied-volatility calibration did not converge after "
            f"{iterations} iterations; pricing residual={pricing_residual:g}"
        )


@dataclass(frozen=True, slots=True)
class ImpliedVolatilityConfig:
    """Volatility bracket and price-space convergence criterion."""

    lower_bound: float = 0.01
    upper_bound: float = 3.0
    tolerance: float = 1e-6
    max_iterations: int = 100

    def __post_init__(self) -> None:
        for name in ("lower_bound", "upper_bound", "tolerance"):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not isfinite(value)
            ):
                raise ValueError(f"{name} must be finite")
        if self.lower_bound <= 0:
            raise ValueError("lower_bound must be positive")
        if self.upper_bound <= self.lower_bound:
            raise ValueError("upper_bound must be greater than lower_bound")
        if self.tolerance <= 0:
            raise ValueError("tolerance must be positive")
        if (
            isinstance(self.max_iterations, bool)
            or not isinstance(self.max_iterations, int)
            or self.max_iterations <= 0
        ):
            raise ValueError("max_iterations must be a positive integer")


@dataclass(frozen=True, slots=True)
class ImpliedVolatilityResult:
    """Converged volatility and its final CRR pricing evidence."""

    implied_volatility: float
    market_midpoint: float
    pricing_result: PricingResult
    pricing_residual: float
    iterations: int
    tolerance: float

    @property
    def model_price(self) -> float:
        """Return the final CRR price used to calculate the residual."""
        return self.pricing_result.price


class CRRImpliedVolatilitySolver:
    """Recover volatility by bisecting CRR price against a quote midpoint."""

    def __init__(self, engine: CRRPricingEngine | None = None) -> None:
        self._engine = engine or CRRPricingEngine()

    def solve(
        self,
        request: PricingRequest,
        config: ImpliedVolatilityConfig = ImpliedVolatilityConfig(),
    ) -> ImpliedVolatilityResult:
        if not isinstance(request, PricingRequest):
            raise TypeError("request must be a PricingRequest")
        if not isinstance(config, ImpliedVolatilityConfig):
            raise TypeError("config must be an ImpliedVolatilityConfig")

        market_midpoint = request.market.option_quote.mid()
        if market_midpoint is None:
            raise ImpliedVolatilityError(
                "implied-volatility calibration requires both bid and ask prices"
            )
        if market_midpoint <= 0:
            raise ImpliedVolatilityError(
                "market midpoint must be positive for implied-volatility calibration"
            )

        lower_result = self._price_at_volatility(request, config.lower_bound)
        lower_residual = lower_result.price - market_midpoint
        if abs(lower_residual) <= config.tolerance:
            return self._result(
                config.lower_bound,
                market_midpoint,
                lower_result,
                lower_residual,
                0,
                config,
            )

        upper_result = self._price_at_volatility(request, config.upper_bound)
        upper_residual = upper_result.price - market_midpoint
        if abs(upper_residual) <= config.tolerance:
            return self._result(
                config.upper_bound,
                market_midpoint,
                upper_result,
                upper_residual,
                0,
                config,
            )
        if lower_residual * upper_residual > 0:
            raise ImpliedVolatilityError(
                "market midpoint is not bracketed by CRR prices at the configured "
                "volatility bounds"
            )

        lower = config.lower_bound
        upper = config.upper_bound
        residual = lower_residual
        for iteration in range(1, config.max_iterations + 1):
            volatility = (lower + upper) / 2.0
            pricing_result = self._price_at_volatility(request, volatility)
            residual = pricing_result.price - market_midpoint
            if abs(residual) <= config.tolerance:
                return self._result(
                    volatility,
                    market_midpoint,
                    pricing_result,
                    residual,
                    iteration,
                    config,
                )
            if lower_residual * residual < 0:
                upper = volatility
            else:
                lower = volatility
                lower_residual = residual

        raise ImpliedVolatilityConvergenceError(config.max_iterations, residual)

    def _price_at_volatility(
        self, request: PricingRequest, volatility: float
    ) -> PricingResult:
        market = replace(request.market, volatility_input=volatility)
        candidate = replace(request, market=market)
        try:
            return self._engine.price(candidate)
        except (InvalidTreeParametersError, PricingError) as error:
            raise ImpliedVolatilityError(
                f"CRR pricing failed at volatility {volatility:g}: {error}"
            ) from error

    @staticmethod
    def _result(
        volatility: float,
        market_midpoint: float,
        pricing_result: PricingResult,
        residual: float,
        iterations: int,
        config: ImpliedVolatilityConfig,
    ) -> ImpliedVolatilityResult:
        return ImpliedVolatilityResult(
            implied_volatility=volatility,
            market_midpoint=market_midpoint,
            pricing_result=pricing_result,
            pricing_residual=residual,
            iterations=iterations,
            tolerance=config.tolerance,
        )
