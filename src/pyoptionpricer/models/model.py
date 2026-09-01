"""Canonical pricing-model identifiers and configuration contracts."""

from dataclasses import dataclass
from enum import Enum
from typing import Protocol, runtime_checkable


class PricingModel(str, Enum):
    """Stable identifiers for the pricing models in the Phase-2 platform."""

    CRR = "CRR"
    BLACK_SCHOLES_MERTON = "BLACK_SCHOLES_MERTON"
    MONTE_CARLO = "MONTE_CARLO"


@runtime_checkable
class PricingModelConfiguration(Protocol):
    """Configuration owned by exactly one pricing model."""

    model: PricingModel


@dataclass(frozen=True, slots=True)
class ModelSelection:
    """A canonical model choice coupled to its model-specific configuration."""

    model: PricingModel
    configuration: PricingModelConfiguration

    def __post_init__(self) -> None:
        if not isinstance(self.model, PricingModel):
            raise TypeError("model must be a PricingModel")
        if not isinstance(self.configuration, PricingModelConfiguration):
            raise TypeError(
                "configuration must implement PricingModelConfiguration"
            )
        if self.configuration.model is not self.model:
            raise ValueError("configuration does not belong to the selected model")
