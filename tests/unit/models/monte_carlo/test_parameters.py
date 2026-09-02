import pytest

from pyoptionpricer import (
    InvalidMonteCarloParametersError,
    MonteCarloModelParameters,
    PricingModel,
)


def test_monte_carlo_parameters_select_monte_carlo_model() -> None:
    parameters = MonteCarloModelParameters()

    assert parameters.model is PricingModel.MONTE_CARLO


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"number_of_paths": 1}, "at least two"),
        ({"number_of_paths": 2}, "at least two antithetic pairs"),
        ({"number_of_paths": 3}, "even"),
        ({"time_steps": 0}, "time_steps"),
        ({"random_seed": True}, "random_seed"),
        ({"antithetic_variates": 1}, "antithetic_variates"),
        ({"confidence_level": 1.0}, "confidence_level"),
        ({"confidence_level": float("nan")}, "confidence_level"),
    ],
)
def test_monte_carlo_parameters_reject_invalid_values(
    overrides: dict[str, object], message: str
) -> None:
    with pytest.raises(InvalidMonteCarloParametersError, match=message):
        MonteCarloModelParameters(**overrides)  # type: ignore[arg-type]
