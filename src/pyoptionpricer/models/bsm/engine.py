"""Model-level orchestration for Black-Scholes-Merton valuation."""

from math import isfinite

from pyoptionpricer.domain import ExerciseStyle
from pyoptionpricer.models import BSMModelParameters, PricingModel
from pyoptionpricer.models.bsm.products import BSMInputs, BSM_PRODUCT_PRICERS
from pyoptionpricer.pricing.engines import EngineCapabilities, ModelCapabilityValidator
from pyoptionpricer.pricing.errors import PricingError
from pyoptionpricer.pricing.requests import PricingRequest
from pyoptionpricer.pricing.results import PricingResult


class BSMPricingEngine:
    """Dispatch European products to independent analytical BSM strategies."""

    model = PricingModel.BLACK_SCHOLES_MERTON
    model_name = model.value
    capabilities = EngineCapabilities(
        products=frozenset(BSM_PRODUCT_PRICERS),
        exercise_styles=frozenset({ExerciseStyle.EUROPEAN}),
        supports_path_dependency=False,
        supports_early_exercise=False,
    )

    def price(self, request: PricingRequest) -> PricingResult:
        if not isinstance(request, PricingRequest):
            raise TypeError("request must be a PricingRequest")
        ModelCapabilityValidator().validate_request(self, request)
        if not isinstance(request.model_parameters, BSMModelParameters):
            raise TypeError("BSM requests require BSMModelParameters")

        resolved = request.inputs
        inputs = BSMInputs(
            spot=resolved.spot.value,
            strike=resolved.strike.value,
            maturity=resolved.maturity.value,
            rate=resolved.risk_free_rate.value,
            dividend=resolved.dividend_yield.value,
            volatility=resolved.volatility.value,
        )
        try:
            product_pricer = BSM_PRODUCT_PRICERS[request.instrument.product]
        except KeyError as error:
            raise PricingError(
                f"no BSM product pricer is configured for "
                f"{request.instrument.product.value}"
            ) from error
        calculation = product_pricer.price(
            inputs,
            request.instrument.payoff,
            request.model_parameters,
        )
        if not isfinite(calculation.price) or calculation.price < 0:
            raise PricingError("BSM pricing produced an invalid option value")
        return PricingResult(
            price=calculation.price,
            currency=request.instrument.currency,
            model_name=self.model_name,
            model_parameters=request.model_parameters,
            valuation_datetime=request.market.valuation_datetime,
            inputs=resolved,
            greeks=calculation.greeks,
            diagnostics=calculation.diagnostics,
        )
