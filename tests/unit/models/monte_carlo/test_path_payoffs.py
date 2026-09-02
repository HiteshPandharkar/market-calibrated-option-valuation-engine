import pytest

from pyoptionpricer import OptionType, VanillaPayoff
from pyoptionpricer.models.monte_carlo import (
    ArithmeticAveragePathPayoffEvaluator,
    FixedStrikeLookbackPathPayoffEvaluator,
    GeneratedPath,
)


@pytest.mark.parametrize(
    ("option_type", "expected"),
    [(OptionType.CALL, 10.0), (OptionType.PUT, 0.0)],
)
def test_arithmetic_average_payoff_uses_only_selected_observations(
    option_type: OptionType, expected: float
) -> None:
    path = GeneratedPath((100.0, 80.0, 120.0, 100.0), 0.25)
    evaluator = ArithmeticAveragePathPayoffEvaluator(
        VanillaPayoff(option_type, 100.0), (0, 2)
    )

    assert evaluator.evaluate(path) == expected


def test_arithmetic_average_payoff_supports_one_observation() -> None:
    path = GeneratedPath((100.0, 150.0, 90.0), 0.5)
    evaluator = ArithmeticAveragePathPayoffEvaluator(
        VanillaPayoff(OptionType.PUT, 100.0), (2,)
    )

    assert evaluator.evaluate(path) == 10.0


@pytest.mark.parametrize(
    ("values", "option_type", "expected"),
    [
        ((90.0, 100.0, 120.0), OptionType.CALL, 10.0),
        ((120.0, 100.0, 80.0), OptionType.PUT, 30.0),
        ((105.0, 105.0, 105.0), OptionType.CALL, 0.0),
        ((90.0, 120.0, 95.0), OptionType.CALL, 10.0),
    ],
)
def test_fixed_strike_lookback_payoff_uses_monitored_extremum(
    values: tuple[float, ...], option_type: OptionType, expected: float
) -> None:
    path = GeneratedPath(values, 0.5)
    evaluator = FixedStrikeLookbackPathPayoffEvaluator(
        VanillaPayoff(option_type, 110.0), tuple(range(len(values)))
    )

    assert evaluator.evaluate(path) == expected


@pytest.mark.parametrize(
    "evaluator_type",
    [ArithmeticAveragePathPayoffEvaluator, FixedStrikeLookbackPathPayoffEvaluator],
)
def test_path_payoffs_reject_invalid_monitoring_indices(evaluator_type: type) -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        evaluator_type(VanillaPayoff(OptionType.CALL, 100.0), ())
