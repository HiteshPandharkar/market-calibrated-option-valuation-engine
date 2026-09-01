"""General pricing-engine contracts, capabilities, and strict selection."""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from pyoptionpricer.domain import ExerciseStyle, OptionProduct
from pyoptionpricer.models import PricingModel

if TYPE_CHECKING:
    from pyoptionpricer.pricing.requests import PricingRequest
    from pyoptionpricer.pricing.results import PricingResult


class UnsupportedModelError(LookupError):
    """Raised when the repository has no engine for the selected model."""

    def __init__(
        self,
        model: PricingModel | str,
        available_models: Iterable[PricingModel] = (),
    ) -> None:
        self.model = model
        self.available_models = frozenset(available_models)
        available = ", ".join(sorted(item.value for item in self.available_models))
        model_value = model.value if isinstance(model, PricingModel) else model
        message = f"no pricing engine is available for model {model_value}"
        if available:
            message += f"; available models: {available}"
        super().__init__(message)


class UnsupportedInstrumentModelCombinationError(ValueError):
    """Raised when a model cannot price a product/exercise combination."""

    def __init__(
        self,
        model: PricingModel,
        product: OptionProduct,
        exercise_style: ExerciseStyle,
        reason: str,
    ) -> None:
        self.model = model
        self.product = product
        self.exercise_style = exercise_style
        self.reason = reason
        super().__init__(
            f"{model.value} does not support {exercise_style.value} "
            f"{product.value}: {reason}"
        )


@dataclass(frozen=True, slots=True)
class EngineCapabilities:
    """Products and exercise behavior explicitly supported by one engine."""

    products: frozenset[OptionProduct]
    exercise_styles: frozenset[ExerciseStyle]
    supports_path_dependency: bool
    supports_early_exercise: bool

    def __post_init__(self) -> None:
        if not self.products:
            raise ValueError("products must contain at least one product")
        if not self.exercise_styles:
            raise ValueError("exercise_styles must contain at least one style")
        if not all(isinstance(item, OptionProduct) for item in self.products):
            raise TypeError("products must contain only OptionProduct values")
        if not all(
            isinstance(item, ExerciseStyle) for item in self.exercise_styles
        ):
            raise TypeError(
                "exercise_styles must contain only ExerciseStyle values"
            )
        if not isinstance(self.supports_path_dependency, bool):
            raise TypeError("supports_path_dependency must be a bool")
        if not isinstance(self.supports_early_exercise, bool):
            raise TypeError("supports_early_exercise must be a bool")


@runtime_checkable
class PricingEngine(Protocol):
    """Narrow engine interface consumed by model-neutral orchestration."""

    model: PricingModel
    capabilities: EngineCapabilities

    def price(self, request: "PricingRequest") -> "PricingResult": ...


class ModelCapabilityValidator:
    """Validate model/product compatibility independently of engine logic."""

    def validate(
        self,
        model: PricingModel,
        capabilities: EngineCapabilities,
        product: OptionProduct,
        exercise_style: ExerciseStyle,
    ) -> None:
        if product not in capabilities.products:
            raise UnsupportedInstrumentModelCombinationError(
                model,
                product,
                exercise_style,
                "product family is not supported",
            )
        if exercise_style not in capabilities.exercise_styles:
            raise UnsupportedInstrumentModelCombinationError(
                model,
                product,
                exercise_style,
                "exercise style is not supported",
            )

    def validate_request(
        self, engine: PricingEngine, request: "PricingRequest"
    ) -> None:
        if request.model is not engine.model:
            raise UnsupportedInstrumentModelCombinationError(
                engine.model,
                request.instrument.product,
                request.instrument.exercise_style,
                f"request selected model {request.model.value}",
            )
        self.validate(
            engine.model,
            engine.capabilities,
            request.instrument.product,
            request.instrument.exercise_style,
        )
