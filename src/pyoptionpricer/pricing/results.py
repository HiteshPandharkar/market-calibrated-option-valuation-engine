"""Structured outputs from pricing engines."""

from dataclasses import dataclass
from datetime import datetime
from math import isfinite

from pyoptionpricer.domain import (
    BarrierDirection,
    BarrierKnockType,
    BarrierMonitoringConvention,
    Currency,
)
from pyoptionpricer.models import PricingModel, PricingModelConfiguration
from pyoptionpricer.models.tree import CRRTreeParameters
from pyoptionpricer.pricing.greeks import OptionGreeks
from pyoptionpricer.pricing.requests import PricingInputs


@dataclass(frozen=True, slots=True)
class PricingDiagnostics:
    """Core tree diagnostics available independently of presentation code."""

    tree_parameters: CRRTreeParameters
    early_exercise_nodes: int


@dataclass(frozen=True, slots=True)
class BarrierPricingDiagnostics(PricingDiagnostics):
    """CRR assumptions and grid warnings for a single-barrier valuation."""

    barrier_level: float
    barrier_direction: BarrierDirection
    knock_type: BarrierKnockType
    monitoring_convention: BarrierMonitoringConvention
    rebate: float
    tree_steps: int
    grid_alignment_warnings: tuple[str, ...]
    rebate_timing: str

    @property
    def barrier_type(self) -> str:
        """Return the canonical combined direction/knock identifier."""
        return f"{self.barrier_direction.value}_AND_{self.knock_type.value}"


@dataclass(frozen=True, slots=True)
class BSMPricingDiagnostics:
    """Auditable analytical quantities and numerical path used by BSM."""

    calculation_mode: str
    spot_discount_factor: float
    strike_discount_factor: float
    d1: float | None
    d2: float | None

    def __post_init__(self) -> None:
        if self.calculation_mode not in {"ANALYTICAL", "DETERMINISTIC_LIMIT"}:
            raise ValueError("calculation_mode must identify a BSM numerical path")
        if any(
            not isfinite(value) or value < 0
            for value in (self.spot_discount_factor, self.strike_discount_factor)
        ):
            raise ValueError("BSM discount factors must be finite and non-negative")
        if self.calculation_mode == "ANALYTICAL":
            if self.d1 is None or self.d2 is None:
                raise ValueError("analytical BSM diagnostics require d1 and d2")
            if not isfinite(self.d1) or not isfinite(self.d2):
                raise ValueError("BSM d1 and d2 must be finite")
        elif self.d1 is not None or self.d2 is not None:
            raise ValueError("deterministic-limit diagnostics do not define d1 or d2")


@dataclass(frozen=True, slots=True)
class MonteCarloPricingDiagnostics:
    """Estimate uncertainty and reproducibility metadata for a simulation."""

    estimated_price: float
    standard_error: float
    confidence_interval: tuple[float, float]
    number_of_paths: int
    time_steps: int
    seed: int
    variance_reduction_method: str
    confidence_level: float

    def __post_init__(self) -> None:
        lower, upper = self.confidence_interval
        if any(
            not isfinite(value)
            for value in (
                self.estimated_price,
                self.standard_error,
                lower,
                upper,
                self.confidence_level,
            )
        ):
            raise ValueError("Monte Carlo statistics must be finite")
        if self.estimated_price < 0 or self.standard_error < 0:
            raise ValueError(
                "Monte Carlo estimate and standard error must be non-negative"
            )
        if lower > self.estimated_price or upper < self.estimated_price:
            raise ValueError("confidence_interval must contain estimated_price")
        if self.number_of_paths <= 0 or self.time_steps <= 0:
            raise ValueError("Monte Carlo path and time-step counts must be positive")
        if self.variance_reduction_method not in {"NONE", "ANTITHETIC_VARIATES"}:
            raise ValueError("unsupported variance_reduction_method")
        if not 0.0 < self.confidence_level < 1.0:
            raise ValueError("confidence_level must be strictly between zero and one")


@dataclass(frozen=True, slots=True)
class PricingResult:
    """Structured theoretical value and its reproducibility metadata."""

    price: float
    currency: Currency
    model_name: str
    model_parameters: PricingModelConfiguration
    valuation_datetime: datetime
    inputs: PricingInputs
    greeks: OptionGreeks
    diagnostics: (
        PricingDiagnostics
        | BarrierPricingDiagnostics
        | BSMPricingDiagnostics
        | MonteCarloPricingDiagnostics
    )

    @property
    def model(self) -> PricingModel:
        """Return the canonical identifier associated with result metadata."""
        return self.model_parameters.model
