"""Repository-owned routing table for available pricing engines.

This module is the single composition point for making a pricing model
available through :class:`PricingEngineRegistry`. Adding an engine class
elsewhere does not make it selectable; its builder must be added here.
"""

from collections.abc import Callable, Mapping
from types import MappingProxyType
from typing import Final

from pyoptionpricer.models import PricingModel
from pyoptionpricer.models.bsm.engine import BSMPricingEngine
from pyoptionpricer.models.monte_carlo.engine import MonteCarloPricingEngine
from pyoptionpricer.pricing.engines import EngineCapabilities, PricingEngine
from pyoptionpricer.models.tree.pricing_engine import CRRPricingEngine


EngineBuilder = Callable[[], PricingEngine]


PRICING_ENGINE_ROUTES: Final[Mapping[PricingModel, EngineBuilder]] = (
    MappingProxyType(
        {
            PricingModel.CRR: CRRPricingEngine,
            PricingModel.BLACK_SCHOLES_MERTON: BSMPricingEngine,
            PricingModel.MONTE_CARLO: MonteCarloPricingEngine,
        }
    )
)
"""Immutable model-to-builder routes for engines shipped by the repository."""


def resolve_pricing_model(model: PricingModel | str) -> PricingModel:
    """Normalize an enum member or one of its exact string values."""
    if isinstance(model, PricingModel):
        return model
    if not isinstance(model, str):
        raise TypeError("model must be a PricingModel or string value")
    try:
        return PricingModel(model.strip())
    except ValueError as error:
        from pyoptionpricer.pricing.engines import UnsupportedModelError

        raise UnsupportedModelError(model, PRICING_ENGINE_ROUTES) from error


def build_available_pricing_engine(
    model: PricingModel | str,
) -> PricingEngine:
    """Construct only the repository engine selected by ``model``."""
    selected_model = resolve_pricing_model(model)
    try:
        builder = PRICING_ENGINE_ROUTES[selected_model]
    except KeyError as error:
        from pyoptionpricer.pricing.engines import UnsupportedModelError

        raise UnsupportedModelError(
            selected_model, PRICING_ENGINE_ROUTES
        ) from error

    engine = builder()
    if not isinstance(engine, PricingEngine):
        raise TypeError(
            f"engine routed for {selected_model.value} must implement PricingEngine"
        )
    if engine.model is not selected_model:
        raise ValueError(
            f"engine routed for {selected_model.value} identifies itself as "
            f"{engine.model.value}"
        )
    if not isinstance(engine.capabilities, EngineCapabilities):
        raise TypeError(
            f"engine routed for {selected_model.value} must declare "
            "EngineCapabilities"
        )
    return engine
