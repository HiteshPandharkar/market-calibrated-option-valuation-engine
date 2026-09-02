"""Provider-neutral Monte Carlo pricing orchestration."""

from datetime import date
from math import exp, isfinite, log, sqrt
from statistics import NormalDist, fmean, variance

from pyoptionpricer.domain import (
    AsianOptionContract,
    ExerciseStyle,
    LookbackOptionContract,
    OptionProduct,
)
from pyoptionpricer.models import PricingModel
from pyoptionpricer.models.monte_carlo.parameters import MonteCarloModelParameters
from pyoptionpricer.models.monte_carlo.paths import GeneratedPath, PathGenerator
from pyoptionpricer.models.monte_carlo.payoffs import (
    ArithmeticAveragePathPayoffEvaluator,
    FixedStrikeLookbackPathPayoffEvaluator,
    PathPayoffEvaluator,
    TerminalPathPayoffEvaluator,
)
from pyoptionpricer.models.monte_carlo.processes import GeometricBrownianMotion
from pyoptionpricer.models.monte_carlo.random_numbers import PythonRandomNumberGenerator
from pyoptionpricer.pricing.engines import EngineCapabilities, ModelCapabilityValidator
from pyoptionpricer.pricing.errors import PricingError
from pyoptionpricer.pricing.greeks import OptionGreeks
from pyoptionpricer.pricing.requests import PricingRequest
from pyoptionpricer.pricing.results import (
    AsianMonteCarloPricingDiagnostics,
    LookbackMonteCarloPricingDiagnostics,
    MonteCarloPricingDiagnostics,
    PricingResult,
)


class MonteCarloPricingEngine:
    """Price supported European contracts from reusable simulated paths."""

    model = PricingModel.MONTE_CARLO
    model_name = model.value
    capabilities = EngineCapabilities(
        products=frozenset(
            {OptionProduct.VANILLA, OptionProduct.ASIAN, OptionProduct.LOOKBACK}
        ),
        exercise_styles=frozenset({ExerciseStyle.EUROPEAN}),
        supports_path_dependency=True,
        supports_early_exercise=False,
    )

    def price(self, request: PricingRequest) -> PricingResult:
        if not isinstance(request, PricingRequest):
            raise TypeError("request must be a PricingRequest")
        ModelCapabilityValidator().validate_request(self, request)
        parameters = request.model_parameters
        if not isinstance(parameters, MonteCarloModelParameters):
            raise TypeError("Monte Carlo requests require MonteCarloModelParameters")

        inputs = request.inputs
        process = GeometricBrownianMotion(
            inputs.risk_free_rate.value,
            inputs.dividend_yield.value,
            inputs.volatility.value,
        )
        paths = PathGenerator(
            process, PythonRandomNumberGenerator(parameters.random_seed)
        ).generate(
            initial_spot=inputs.spot.value,
            maturity=inputs.maturity.value,
            time_steps=parameters.time_steps,
            number_of_paths=parameters.number_of_paths,
            antithetic_variates=parameters.antithetic_variates,
        )
        discount = exp(-inputs.risk_free_rate.value * inputs.maturity.value)
        spot_bump = max(inputs.spot.value * 1e-4, 1e-8)
        theta_step = min(1.0 / 365.0, inputs.maturity.value / 2.0)
        grouped: list[float] = []
        grouped_up: list[float] = []
        grouped_down: list[float] = []
        grouped_short: list[float] = []
        group_size = 2 if parameters.antithetic_variates else 1
        pending: list[tuple[float, float, float, float]] = []
        payoff_evaluator = self._payoff_evaluator(request, parameters.time_steps)

        try:
            for path in paths:
                base = discount * payoff_evaluator.evaluate(path)
                up = discount * payoff_evaluator.evaluate(
                    self._scale_path(
                        path, (inputs.spot.value + spot_bump) / inputs.spot.value
                    )
                )
                down = discount * payoff_evaluator.evaluate(
                    self._scale_path(
                        path, (inputs.spot.value - spot_bump) / inputs.spot.value
                    )
                )
                reduced_maturity = inputs.maturity.value - theta_step
                short_path = self._shorten_path(
                    path,
                    initial_spot=inputs.spot.value,
                    original_maturity=inputs.maturity.value,
                    reduced_maturity=reduced_maturity,
                    risk_free_rate=inputs.risk_free_rate.value,
                    dividend_yield=inputs.dividend_yield.value,
                    volatility=inputs.volatility.value,
                )
                short = exp(
                    -inputs.risk_free_rate.value * reduced_maturity
                ) * payoff_evaluator.evaluate(short_path)
                pending.append((base, up, down, short))
                if len(pending) == group_size:
                    grouped.append(fmean(item[0] for item in pending))
                    grouped_up.append(fmean(item[1] for item in pending))
                    grouped_down.append(fmean(item[2] for item in pending))
                    grouped_short.append(fmean(item[3] for item in pending))
                    pending.clear()
        except (ArithmeticError, OverflowError, ValueError) as error:
            raise PricingError("Monte Carlo simulation failed") from error

        estimate = fmean(grouped)
        standard_error = sqrt(variance(grouped) / len(grouped))
        critical_value = NormalDist().inv_cdf(
            0.5 + parameters.confidence_level / 2.0
        )
        half_width = critical_value * standard_error
        up_price = fmean(grouped_up)
        down_price = fmean(grouped_down)
        short_price = fmean(grouped_short)
        delta = (up_price - down_price) / (2.0 * spot_bump)
        gamma = (up_price - 2.0 * estimate + down_price) / spot_bump**2
        theta = (short_price - estimate) / theta_step
        values = (estimate, standard_error, delta, gamma, theta)
        if any(not isfinite(value) for value in values) or estimate < 0:
            raise PricingError("Monte Carlo pricing produced an invalid result")

        diagnostic_values = dict(
            estimated_price=estimate,
            standard_error=standard_error,
            confidence_interval=(estimate - half_width, estimate + half_width),
            number_of_paths=parameters.number_of_paths,
            time_steps=parameters.time_steps,
            seed=parameters.random_seed,
            variance_reduction_method=(
                "ANTITHETIC_VARIATES"
                if parameters.antithetic_variates
                else "NONE"
            ),
            confidence_level=parameters.confidence_level,
        )
        instrument = request.instrument
        if isinstance(instrument, AsianOptionContract):
            diagnostics = AsianMonteCarloPricingDiagnostics(
                **diagnostic_values,
                observation_count=len(instrument.observation_schedule),
                averaging_method=instrument.averaging_method,
                monitoring_convention=instrument.monitoring_convention,
            )
        elif isinstance(instrument, LookbackOptionContract):
            diagnostics = LookbackMonteCarloPricingDiagnostics(
                **diagnostic_values,
                monitoring_count=len(instrument.monitoring_schedule),
                monitoring_convention=instrument.monitoring_convention,
            )
        else:
            diagnostics = MonteCarloPricingDiagnostics(**diagnostic_values)
        return PricingResult(
            price=estimate,
            currency=request.instrument.currency,
            model_name=self.model_name,
            model_parameters=parameters,
            valuation_datetime=request.market.valuation_datetime,
            inputs=inputs,
            greeks=OptionGreeks(delta=delta, gamma=gamma, theta=theta),
            diagnostics=diagnostics,
        )

    @staticmethod
    def _payoff_evaluator(
        request: PricingRequest, time_steps: int
    ) -> PathPayoffEvaluator:
        instrument = request.instrument
        if isinstance(instrument, AsianOptionContract):
            indices = MonteCarloPricingEngine._schedule_indices(
                instrument.observation_schedule, request, time_steps
            )
            return ArithmeticAveragePathPayoffEvaluator(instrument.payoff, indices)
        if isinstance(instrument, LookbackOptionContract):
            indices = MonteCarloPricingEngine._schedule_indices(
                instrument.monitoring_schedule, request, time_steps
            )
            return FixedStrikeLookbackPathPayoffEvaluator(instrument.payoff, indices)
        return TerminalPathPayoffEvaluator(instrument.payoff)

    @staticmethod
    def _schedule_indices(
        schedule: tuple[date, ...], request: PricingRequest, time_steps: int
    ) -> tuple[int, ...]:
        valuation_date = request.market.valuation_datetime.date()
        maturity_days = (request.instrument.expiry - valuation_date).days
        indices: list[int] = []
        for monitoring_date in schedule:
            offset_days = (monitoring_date - valuation_date).days
            if offset_days < 0:
                raise PricingError("monitoring schedules must not precede valuation")
            numerator = offset_days * time_steps
            if numerator % maturity_days:
                raise PricingError(
                    "monitoring schedule dates must align exactly with Monte Carlo grid nodes"
                )
            indices.append(numerator // maturity_days)
        return tuple(indices)

    @staticmethod
    def _scale_path(path: GeneratedPath, factor: float) -> GeneratedPath:
        return GeneratedPath(
            tuple(value * factor for value in path.values), path.time_step
        )

    @staticmethod
    def _shorten_path(
        path: GeneratedPath,
        *,
        initial_spot: float,
        original_maturity: float,
        reduced_maturity: float,
        risk_free_rate: float,
        dividend_yield: float,
        volatility: float,
    ) -> GeneratedPath:
        time_scale = reduced_maturity / original_maturity
        drift_rate = risk_free_rate - dividend_yield - 0.5 * volatility**2
        values = [initial_spot]
        for index, spot in enumerate(path.values[1:], start=1):
            original_time = index * path.time_step
            brownian_component = log(spot / initial_spot) - drift_rate * original_time
            values.append(
                initial_spot
                * exp(
                    drift_rate * original_time * time_scale
                    + sqrt(time_scale) * brownian_component
                )
            )
        return GeneratedPath(tuple(values), path.time_step * time_scale)
