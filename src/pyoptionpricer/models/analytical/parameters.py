"""Validated configuration for the Black-Scholes-Merton model."""

from dataclasses import dataclass
from math import isfinite
from typing import ClassVar

from pyoptionpricer.models.model import PricingModel


class InvalidBSMParametersError(ValueError):
    """Raised when BSM numerical-boundary settings are invalid."""


@dataclass(frozen=True, slots=True)
class BSMModelParameters:
    """Numerical boundary policy for analytical BSM valuation.

    Inputs at or below either threshold are evaluated with the deterministic
    discounted-payoff limit instead of dividing by a vanishing standard
    deviation. The thresholds are explicit configuration, not hidden clamps.
    """

    model: ClassVar[PricingModel] = PricingModel.BLACK_SCHOLES_MERTON
    near_zero_maturity: float = 1e-10
    near_zero_volatility: float = 1e-10

    def __post_init__(self) -> None:
        for name in ("near_zero_maturity", "near_zero_volatility"):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not isfinite(value)
                or value < 0
            ):
                raise InvalidBSMParametersError(
                    f"{name} must be a finite non-negative number"
                )
