"""Analytical Black-Scholes-Merton valuation for European vanilla options."""

from math import erfc, exp, isfinite, log, pi, sqrt

from pyoptionpricer.domain import ExerciseStyle, OptionProduct, OptionType
from pyoptionpricer.models import BSMModelParameters, PricingModel
from pyoptionpricer.pricing.engines import EngineCapabilities, ModelCapabilityValidator
from pyoptionpricer.pricing.errors import PricingError
from pyoptionpricer.pricing.greeks import OptionGreeks
from pyoptionpricer.pricing.requests import PricingRequest
from pyoptionpricer.pricing.results import BSMPricingDiagnostics, PricingResult


class BSMPricingEngine:
    """Price European vanilla options from normalized project-owned inputs."""

    model = PricingModel.BLACK_SCHOLES_MERTON
    model_name = model.value
    capabilities = EngineCapabilities(
        products=frozenset({OptionProduct.VANILLA}),
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

        inputs = request.inputs
        spot = inputs.spot.value
        strike = inputs.strike.value
        maturity = inputs.maturity.value
        rate = inputs.risk_free_rate.value
        dividend = inputs.dividend_yield.value
        volatility = inputs.volatility.value
        self._validate_inputs(spot, strike, maturity, rate, dividend, volatility)

        spot_discount = self._discount_factor(dividend, maturity, "dividend yield")
        strike_discount = self._discount_factor(rate, maturity, "risk-free rate")
        parameters = request.model_parameters
        if (
            maturity <= parameters.near_zero_maturity
            or volatility <= parameters.near_zero_volatility
        ):
            price, greeks = self._deterministic_limit(
                spot,
                strike,
                maturity,
                rate,
                dividend,
                spot_discount,
                strike_discount,
                request.instrument.option_type,
            )
            diagnostics = BSMPricingDiagnostics(
                "DETERMINISTIC_LIMIT",
                spot_discount,
                strike_discount,
                None,
                None,
            )
        else:
            price, greeks, d1, d2 = self._analytical_value(
                spot,
                strike,
                maturity,
                rate,
                dividend,
                volatility,
                spot_discount,
                strike_discount,
                request.instrument.option_type,
            )
            diagnostics = BSMPricingDiagnostics(
                "ANALYTICAL", spot_discount, strike_discount, d1, d2
            )

        if not isfinite(price) or price < 0:
            raise PricingError("BSM pricing produced an invalid option value")
        return PricingResult(
            price=price,
            currency=request.instrument.currency,
            model_name=self.model_name,
            model_parameters=parameters,
            valuation_datetime=request.market.valuation_datetime,
            inputs=inputs,
            greeks=greeks,
            diagnostics=diagnostics,
        )

    @staticmethod
    def _validate_inputs(
        spot: float,
        strike: float,
        maturity: float,
        rate: float,
        dividend: float,
        volatility: float,
    ) -> None:
        values = (spot, strike, maturity, rate, dividend, volatility)
        if any(not isfinite(value) for value in values):
            raise PricingError("BSM inputs must be finite")
        if spot <= 0:
            raise PricingError("BSM spot must be positive")
        if strike <= 0:
            raise PricingError("BSM strike must be positive")
        if maturity < 0:
            raise PricingError("BSM time to expiry must be non-negative")
        if volatility < 0:
            raise PricingError("BSM volatility must be non-negative")

    @staticmethod
    def _discount_factor(rate: float, maturity: float, name: str) -> float:
        try:
            factor = exp(-rate * maturity)
        except OverflowError as error:
            raise PricingError(
                f"{name} is outside the numerically supported range"
            ) from error
        if not isfinite(factor):
            raise PricingError(f"{name} produced an invalid discount factor")
        return factor

    @classmethod
    def _analytical_value(
        cls,
        spot: float,
        strike: float,
        maturity: float,
        rate: float,
        dividend: float,
        volatility: float,
        spot_discount: float,
        strike_discount: float,
        option_type: OptionType,
    ) -> tuple[float, OptionGreeks, float, float]:
        root_maturity = sqrt(maturity)
        standard_deviation = volatility * root_maturity
        try:
            d1 = (
                log(spot / strike)
                + (rate - dividend + 0.5 * volatility**2) * maturity
            ) / standard_deviation
        except (OverflowError, ZeroDivisionError) as error:
            raise PricingError("BSM standardized moneyness is not computable") from error
        d2 = d1 - standard_deviation
        if not isfinite(d1) or not isfinite(d2):
            raise PricingError("BSM standardized moneyness must be finite")

        n_d1 = cls._normal_cdf(d1)
        n_d2 = cls._normal_cdf(d2)
        density = exp(-0.5 * d1 * d1) / sqrt(2.0 * pi)
        discounted_spot = spot * spot_discount
        discounted_strike = strike * strike_discount
        gamma = spot_discount * density / (spot * standard_deviation)
        vega = discounted_spot * density * root_maturity
        common_theta = -discounted_spot * density * volatility / (2.0 * root_maturity)

        if option_type is OptionType.CALL:
            price = discounted_spot * n_d1 - discounted_strike * n_d2
            delta = spot_discount * n_d1
            theta = (
                common_theta
                - rate * discounted_strike * n_d2
                + dividend * discounted_spot * n_d1
            )
            rho = strike * maturity * strike_discount * n_d2
        else:
            n_minus_d1 = cls._normal_cdf(-d1)
            n_minus_d2 = cls._normal_cdf(-d2)
            price = discounted_strike * n_minus_d2 - discounted_spot * n_minus_d1
            delta = -spot_discount * n_minus_d1
            theta = (
                common_theta
                + rate * discounted_strike * n_minus_d2
                - dividend * discounted_spot * n_minus_d1
            )
            rho = -strike * maturity * strike_discount * n_minus_d2
        return price, OptionGreeks(delta, gamma, theta, vega, rho), d1, d2

    @staticmethod
    def _deterministic_limit(
        spot: float,
        strike: float,
        maturity: float,
        rate: float,
        dividend: float,
        spot_discount: float,
        strike_discount: float,
        option_type: OptionType,
    ) -> tuple[float, OptionGreeks]:
        discounted_spot = spot * spot_discount
        discounted_strike = strike * strike_discount
        forward_intrinsic = discounted_spot - discounted_strike
        if forward_intrinsic > 0:
            call_weight = 1.0
        elif forward_intrinsic < 0:
            call_weight = 0.0
        else:
            call_weight = 0.5

        if option_type is OptionType.CALL:
            weight = call_weight
            price = max(forward_intrinsic, 0.0)
            delta = weight * spot_discount
            theta = weight * (
                dividend * discounted_spot - rate * discounted_strike
            )
            rho = weight * strike * maturity * strike_discount
        else:
            weight = 1.0 - call_weight
            price = max(-forward_intrinsic, 0.0)
            delta = -weight * spot_discount
            theta = weight * (
                rate * discounted_strike - dividend * discounted_spot
            )
            rho = -weight * strike * maturity * strike_discount
        return price, OptionGreeks(delta, 0.0, theta, 0.0, rho)

    @staticmethod
    def _normal_cdf(value: float) -> float:
        return 0.5 * erfc(-value / sqrt(2.0))
