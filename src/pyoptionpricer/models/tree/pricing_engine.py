"""Backward-induction pricing for supported exercise styles and payoffs."""

from math import isfinite

from pyoptionpricer.domain import ExerciseStyle, OptionProduct
from pyoptionpricer.models import PricingModel
from pyoptionpricer.models.tree import calculate_crr_tree_parameters
from pyoptionpricer.pricing.engines import EngineCapabilities, ModelCapabilityValidator
from pyoptionpricer.pricing.errors import PricingError
from pyoptionpricer.pricing.exercise import (
    ExerciseScheduleMappingError,
    exercise_policy,
    map_bermudan_exercise_steps,
)
from pyoptionpricer.pricing.greeks import GreekCalculationError, calculate_tree_greeks
from pyoptionpricer.pricing.requests import PricingRequest
from pyoptionpricer.pricing.results import PricingDiagnostics, PricingResult


class CRRPricingEngine:
    """Price complete provider-neutral requests with a recombining CRR tree."""

    model = PricingModel.CRR
    model_name = model.value
    capabilities = EngineCapabilities(
        products=frozenset({OptionProduct.VANILLA, OptionProduct.DIGITAL}),
        exercise_styles=frozenset(
            {
                ExerciseStyle.EUROPEAN,
                ExerciseStyle.AMERICAN,
                ExerciseStyle.BERMUDAN,
            }
        ),
        supports_path_dependency=False,
        supports_early_exercise=True,
    )

    def price(self, request: PricingRequest) -> PricingResult:
        if not isinstance(request, PricingRequest):
            raise TypeError("request must be a PricingRequest")
        ModelCapabilityValidator().validate_request(self, request)

        inputs = request.inputs
        tree = calculate_crr_tree_parameters(
            inputs.maturity.value,
            inputs.risk_free_rate.value,
            inputs.dividend_yield.value,
            inputs.volatility.value,
            request.model_parameters,
        )
        steps = request.model_parameters.steps
        if steps < 2:
            raise PricingError("at least two CRR steps are required to calculate Greeks")
        spot = inputs.spot.value
        payoff = request.instrument.payoff

        try:
            values = [
                payoff.value_at(
                    spot
                    * tree.up_factor**up_moves
                    * tree.down_factor ** (steps - up_moves)
                )
                for up_moves in range(steps + 1)
            ]
        except OverflowError as error:
            raise PricingError("terminal lattice construction overflowed") from error

        early_exercise_nodes = 0
        first_level_values: tuple[float, float] | None = None
        second_level_values: tuple[float, float, float] | None = None
        probability = tree.risk_neutral_probability
        bermudan_steps = frozenset()
        if request.instrument.exercise_style is ExerciseStyle.BERMUDAN:
            schedule = request.instrument.exercise_schedule
            if schedule is None:  # Protected by OptionContract validation.
                raise PricingError("Bermudan contract requires an exercise schedule")
            try:
                bermudan_steps = map_bermudan_exercise_steps(
                    schedule,
                    request.market.valuation_datetime.date(),
                    request.instrument.expiry,
                    steps,
                )
            except ExerciseScheduleMappingError as error:
                raise PricingError(str(error)) from error
        policy = exercise_policy(request.instrument.exercise_style, bermudan_steps)
        for time_index in range(steps - 1, -1, -1):
            next_values: list[float] = []
            for up_moves in range(time_index + 1):
                continuation = tree.discount_factor * (
                    probability * values[up_moves + 1]
                    + (1.0 - probability) * values[up_moves]
                )
                try:
                    node_spot = (
                        spot
                        * tree.up_factor**up_moves
                        * tree.down_factor ** (time_index - up_moves)
                    )
                except OverflowError as error:
                    raise PricingError("lattice backward induction overflowed") from error
                intrinsic = payoff.value_at(node_spot)
                node_value, exercised = policy.node_value(
                    continuation, intrinsic, time_index
                )
                early_exercise_nodes += int(exercised)
                next_values.append(node_value)
            values = next_values
            if time_index == 2:
                second_level_values = (values[0], values[1], values[2])
            elif time_index == 1:
                first_level_values = (values[0], values[1])

        price = values[0]
        if not isfinite(price) or price < 0:
            raise PricingError("pricing produced an invalid option value")
        if first_level_values is None or second_level_values is None:
            raise PricingError("tree levels required for Greeks are unavailable")
        first_level_spots = (spot * tree.down_factor, spot * tree.up_factor)
        second_level_spots = (
            spot * tree.down_factor**2,
            spot * tree.down_factor * tree.up_factor,
            spot * tree.up_factor**2,
        )
        try:
            greeks = calculate_tree_greeks(
                price,
                first_level_values,
                second_level_values,
                first_level_spots,
                second_level_spots,
                tree.time_step,
            )
        except GreekCalculationError as error:
            raise PricingError("tree Greeks could not be calculated reliably") from error
        return PricingResult(
            price=price,
            currency=request.instrument.currency,
            model_name=self.model_name,
            model_parameters=request.model_parameters,
            valuation_datetime=request.market.valuation_datetime,
            inputs=inputs,
            greeks=greeks,
            diagnostics=PricingDiagnostics(tree, early_exercise_nodes),
        )
