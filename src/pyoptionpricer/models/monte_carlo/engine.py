"""Provider-neutral Monte Carlo pricing orchestration."""

from math import exp, isfinite, log, sqrt
from statistics import NormalDist, fmean, variance

from pyoptionpricer.domain import ExerciseStyle, OptionProduct
from pyoptionpricer.models import PricingModel
from pyoptionpricer.models.monte_carlo.parameters import MonteCarloModelParameters
from pyoptionpricer.models.monte_carlo.paths import PathGenerator
from pyoptionpricer.models.monte_carlo.payoffs import TerminalPathPayoffEvaluator
from pyoptionpricer.models.monte_carlo.processes import GeometricBrownianMotion
from pyoptionpricer.models.monte_carlo.random_numbers import PythonRandomNumberGenerator
from pyoptionpricer.pricing.engines import EngineCapabilities, ModelCapabilityValidator
from pyoptionpricer.pricing.errors import PricingError
from pyoptionpricer.pricing.greeks import OptionGreeks
from pyoptionpricer.pricing.requests import PricingRequest
from pyoptionpricer.pricing.results import MonteCarloPricingDiagnostics, PricingResult


class MonteCarloPricingEngine:
    """Price European vanilla options from reusable simulated paths."""

    model = PricingModel.MONTE_CARLO
    model_name = model.value
    capabilities = EngineCapabilities(
        products=frozenset({OptionProduct.VANILLA}),
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
        payoff = request.instrument.payoff
        payoff_evaluator = TerminalPathPayoffEvaluator(payoff)

        try:
            for path in paths:
                terminal = path.terminal_value
                multiplier = terminal / inputs.spot.value
                base = discount * payoff_evaluator.evaluate(path)
                up = discount * payoff.value_at(
                    (inputs.spot.value + spot_bump) * multiplier
                )
                down = discount * payoff.value_at(
                    (inputs.spot.value - spot_bump) * multiplier
                )
                reduced_maturity = inputs.maturity.value - theta_step
                total_brownian = (
                    log(multiplier)
                    - (
                        inputs.risk_free_rate.value
                        - inputs.dividend_yield.value
                        - 0.5 * inputs.volatility.value**2
                    )
                    * inputs.maturity.value
                ) / inputs.volatility.value
                short_terminal = inputs.spot.value * exp(
                    (
                        inputs.risk_free_rate.value
                        - inputs.dividend_yield.value
                        - 0.5 * inputs.volatility.value**2
                    )
                    * reduced_maturity
                    + inputs.volatility.value
                    * sqrt(reduced_maturity / inputs.maturity.value)
                    * total_brownian
                )
                short = exp(
                    -inputs.risk_free_rate.value * reduced_maturity
                ) * payoff.value_at(short_terminal)
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

        diagnostics = MonteCarloPricingDiagnostics(
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
