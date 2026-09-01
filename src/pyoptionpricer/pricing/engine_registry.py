"""Strict selection and dispatch over repository-routed pricing engines."""

from typing import TYPE_CHECKING, final

from pyoptionpricer.models import PricingModel
from pyoptionpricer.pricing.engine_router import (
    PRICING_ENGINE_ROUTES,
    build_available_pricing_engine,
    resolve_pricing_model,
)
from pyoptionpricer.pricing.engines import (
    ModelCapabilityValidator,
    PricingEngine,
)

if TYPE_CHECKING:
    from pyoptionpricer.pricing.requests import PricingRequest
    from pyoptionpricer.pricing.results import PricingResult


@final
class PricingEngineRegistry:
    """Select only pricing engines declared by the repository router."""

    def __init__(self) -> None:
        if type(self) is not PricingEngineRegistry:
            raise TypeError("PricingEngineRegistry cannot be subclassed")
        self._engines: dict[PricingModel, PricingEngine] = {}

    @property
    def models(self) -> frozenset[PricingModel]:
        return frozenset(PRICING_ENGINE_ROUTES)

    def get(self, model: PricingModel | str) -> PricingEngine:
        selected_model = resolve_pricing_model(model)
        engine = self._engines.get(selected_model)
        if engine is None:
            engine = build_available_pricing_engine(selected_model)
            self._engines[selected_model] = engine
        return engine

    def price(self, request: "PricingRequest") -> "PricingResult":
        from pyoptionpricer.pricing.requests import PricingRequest

        if not isinstance(request, PricingRequest):
            raise TypeError("request must be a PricingRequest")
        engine = self.get(request.model)
        ModelCapabilityValidator().validate_request(engine, request)
        return engine.price(request)
