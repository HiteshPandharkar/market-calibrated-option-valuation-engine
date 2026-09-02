"""Stochastic processes used by Monte Carlo path generation."""

from dataclasses import dataclass
from math import exp, isfinite, sqrt


@dataclass(frozen=True, slots=True)
class GeometricBrownianMotion:
    """Risk-neutral GBM using its exact finite-time transition."""

    risk_free_rate: float
    dividend_yield: float
    volatility: float

    def __post_init__(self) -> None:
        for name in ("risk_free_rate", "dividend_yield", "volatility"):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not isfinite(value)
            ):
                raise ValueError(f"{name} must be finite")
        if self.volatility <= 0:
            raise ValueError("volatility must be positive")

    def evolve(self, spot: float, time_step: float, normal: float) -> float:
        if not isfinite(spot) or spot <= 0:
            raise ValueError("spot must be finite and positive")
        if not isfinite(time_step) or time_step <= 0:
            raise ValueError("time_step must be finite and positive")
        if not isfinite(normal):
            raise ValueError("normal must be finite")
        drift = (
            self.risk_free_rate
            - self.dividend_yield
            - 0.5 * self.volatility**2
        ) * time_step
        diffusion = self.volatility * sqrt(time_step) * normal
        value = spot * exp(drift + diffusion)
        if not isfinite(value) or value <= 0:
            raise ArithmeticError("GBM transition produced an invalid spot")
        return value
