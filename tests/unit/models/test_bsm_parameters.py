import pytest

from pyoptionpricer import (
    BSMModelParameters,
    InvalidBSMParametersError,
    PricingModel,
)


def test_bsm_parameters_select_only_bsm() -> None:
    parameters = BSMModelParameters()

    assert parameters.model is PricingModel.BLACK_SCHOLES_MERTON


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("near_zero_maturity", -1.0),
        ("near_zero_maturity", float("nan")),
        ("near_zero_volatility", -1.0),
        ("near_zero_volatility", True),
    ],
)
def test_bsm_parameters_reject_invalid_boundary_thresholds(
    name: str, value: object
) -> None:
    with pytest.raises(InvalidBSMParametersError, match=name):
        BSMModelParameters(**{name: value})  # type: ignore[arg-type]
