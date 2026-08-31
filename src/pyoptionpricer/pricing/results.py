"""Structured outputs from tree pricing engines."""

from dataclasses import dataclass
from datetime import datetime

from pyoptionpricer.domain import Currency
from pyoptionpricer.models.tree import CRRModelParameters, CRRTreeParameters
from pyoptionpricer.pricing.greeks import OptionGreeks
from pyoptionpricer.pricing.requests import PricingInputs


@dataclass(frozen=True, slots=True)
class PricingDiagnostics:
    """Core tree diagnostics available independently of presentation code."""

    tree_parameters: CRRTreeParameters
    early_exercise_nodes: int


@dataclass(frozen=True, slots=True)
class PricingResult:
    """Structured theoretical value and its reproducibility metadata."""

    price: float
    currency: Currency
    model_name: str
    model_parameters: CRRModelParameters
    valuation_datetime: datetime
    inputs: PricingInputs
    greeks: OptionGreeks
    diagnostics: PricingDiagnostics
