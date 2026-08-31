"""Validated configuration and derived parameters for a CRR tree."""

from dataclasses import dataclass
from math import isfinite


class InvalidTreeParametersError(ValueError):
    """Raised when inputs cannot define a valid risk-neutral CRR tree."""


@dataclass(frozen=True, slots=True)
class CRRModelParameters:
    """User-selected CRR configuration."""

    steps: int = 500

    def __post_init__(self) -> None:
        if isinstance(self.steps, bool) or not isinstance(self.steps, int):
            raise InvalidTreeParametersError("steps must be a positive integer")
        if self.steps <= 0:
            raise InvalidTreeParametersError("steps must be a positive integer")


@dataclass(frozen=True, slots=True)
class CRRTreeParameters:
    """Per-step CRR quantities used by backward induction."""

    time_step: float
    up_factor: float
    down_factor: float
    risk_neutral_probability: float
    discount_factor: float

    def __post_init__(self) -> None:
        values = (
            self.time_step,
            self.up_factor,
            self.down_factor,
            self.risk_neutral_probability,
            self.discount_factor,
        )
        if any(not isfinite(value) for value in values):
            raise InvalidTreeParametersError("derived tree parameters must be finite")
        if self.time_step <= 0:
            raise InvalidTreeParametersError("time_step must be positive")
        if not 0.0 <= self.risk_neutral_probability <= 1.0:
            raise InvalidTreeParametersError(
                "risk-neutral probability must be between zero and one"
            )
