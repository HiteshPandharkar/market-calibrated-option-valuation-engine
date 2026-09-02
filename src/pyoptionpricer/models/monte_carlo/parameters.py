"""Validated configuration for Monte Carlo pricing."""

from dataclasses import dataclass
from math import isfinite
from typing import ClassVar

from pyoptionpricer.models.model import PricingModel


class InvalidMonteCarloParametersError(ValueError):
    """Raised when simulation configuration is invalid."""


@dataclass(frozen=True, slots=True)
class MonteCarloModelParameters:
    """User-selected simulation and statistical settings."""

    model: ClassVar[PricingModel] = PricingModel.MONTE_CARLO
    number_of_paths: int = 10_000
    time_steps: int = 252
    random_seed: int = 0
    antithetic_variates: bool = True
    confidence_level: float = 0.95

    def __post_init__(self) -> None:
        for name in ("number_of_paths", "time_steps"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise InvalidMonteCarloParametersError(
                    f"{name} must be a positive integer"
                )
        if self.number_of_paths < 2:
            raise InvalidMonteCarloParametersError(
                "number_of_paths must be at least two to estimate standard error"
            )
        if not isinstance(self.random_seed, int) or isinstance(
            self.random_seed, bool
        ):
            raise InvalidMonteCarloParametersError("random_seed must be an integer")
        if not isinstance(self.antithetic_variates, bool):
            raise InvalidMonteCarloParametersError(
                "antithetic_variates must be a bool"
            )
        if self.antithetic_variates:
            if self.number_of_paths % 2:
                raise InvalidMonteCarloParametersError(
                    "number_of_paths must be even when antithetic variates are enabled"
                )
            if self.number_of_paths < 4:
                raise InvalidMonteCarloParametersError(
                    "number_of_paths must provide at least two antithetic pairs"
                )
        if (
            isinstance(self.confidence_level, bool)
            or not isinstance(self.confidence_level, (int, float))
            or not isfinite(self.confidence_level)
            or not 0.0 < self.confidence_level < 1.0
        ):
            raise InvalidMonteCarloParametersError(
                "confidence_level must be finite and strictly between zero and one"
            )
        object.__setattr__(self, "confidence_level", float(self.confidence_level))
