"""Cox-Ross-Rubinstein parameter calculation."""

from math import exp, isfinite, sqrt

from pyoptionpricer.models.tree.parameters import (
    CRRModelParameters,
    CRRTreeParameters,
    InvalidTreeParametersError,
)


def calculate_crr_tree_parameters(
    maturity: float,
    risk_free_rate: float,
    dividend_yield: float,
    volatility: float,
    model_parameters: CRRModelParameters,
) -> CRRTreeParameters:
    """Calculate and validate the risk-neutral CRR step parameters."""

    inputs = {
        "maturity": maturity,
        "risk_free_rate": risk_free_rate,
        "dividend_yield": dividend_yield,
        "volatility": volatility,
    }
    for name, value in inputs.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise InvalidTreeParametersError(f"{name} must be finite")
        if not isfinite(value):
            raise InvalidTreeParametersError(f"{name} must be finite")
    if maturity <= 0:
        raise InvalidTreeParametersError("maturity must be positive")
    if volatility <= 0:
        raise InvalidTreeParametersError("volatility must be positive")
    if not isinstance(model_parameters, CRRModelParameters):
        raise InvalidTreeParametersError(
            "model_parameters must be CRRModelParameters"
        )

    time_step = maturity / model_parameters.steps
    try:
        up_factor = exp(volatility * sqrt(time_step))
        down_factor = 1.0 / up_factor
        growth_factor = exp((risk_free_rate - dividend_yield) * time_step)
        discount_factor = exp(-risk_free_rate * time_step)
    except OverflowError as error:
        raise InvalidTreeParametersError("tree parameter calculation overflowed") from error

    denominator = up_factor - down_factor
    if denominator == 0.0:
        raise InvalidTreeParametersError("up and down factors must be distinct")
    probability = (growth_factor - down_factor) / denominator
    if not 0.0 <= probability <= 1.0:
        raise InvalidTreeParametersError(
            "risk-neutral probability is outside [0, 1]; CRR no-arbitrage "
            "condition d <= exp((r-q)dt) <= u is violated"
        )

    return CRRTreeParameters(
        time_step=time_step,
        up_factor=up_factor,
        down_factor=down_factor,
        risk_neutral_probability=probability,
        discount_factor=discount_factor,
    )
