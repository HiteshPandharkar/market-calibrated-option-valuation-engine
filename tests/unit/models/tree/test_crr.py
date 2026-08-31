from math import exp, sqrt

import pytest

from pyoptionpricer import (
    CRRModelParameters,
    InvalidTreeParametersError,
    calculate_crr_tree_parameters,
)


def test_crr_parameter_calculation_uses_continuous_cost_of_carry() -> None:
    parameters = calculate_crr_tree_parameters(
        maturity=1.0,
        risk_free_rate=0.05,
        dividend_yield=0.02,
        volatility=0.20,
        model_parameters=CRRModelParameters(steps=4),
    )
    expected_up = exp(0.20 * sqrt(0.25))
    expected_down = 1.0 / expected_up

    assert parameters.time_step == pytest.approx(0.25)
    assert parameters.up_factor == pytest.approx(expected_up)
    assert parameters.down_factor == pytest.approx(expected_down)
    assert parameters.risk_neutral_probability == pytest.approx(
        (exp(0.03 * 0.25) - expected_down) / (expected_up - expected_down)
    )
    assert parameters.discount_factor == pytest.approx(exp(-0.05 * 0.25))


def test_crr_rejects_invalid_risk_neutral_probability() -> None:
    with pytest.raises(InvalidTreeParametersError, match="probability"):
        calculate_crr_tree_parameters(
            maturity=1.0,
            risk_free_rate=1.0,
            dividend_yield=0.0,
            volatility=0.01,
            model_parameters=CRRModelParameters(steps=1),
        )


@pytest.mark.parametrize("steps", [0, -1, 1.5, True])
def test_crr_rejects_invalid_step_count(steps: object) -> None:
    with pytest.raises(InvalidTreeParametersError, match="steps"):
        CRRModelParameters(steps=steps)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("field", "value"),
    [("maturity", 0.0), ("volatility", 0.0), ("volatility", float("nan"))],
)
def test_crr_rejects_invalid_numeric_inputs(field: str, value: float) -> None:
    values = {
        "maturity": 1.0,
        "risk_free_rate": 0.05,
        "dividend_yield": 0.0,
        "volatility": 0.2,
    }
    values[field] = value

    with pytest.raises(InvalidTreeParametersError, match=field):
        calculate_crr_tree_parameters(
            **values, model_parameters=CRRModelParameters(steps=10)
        )
