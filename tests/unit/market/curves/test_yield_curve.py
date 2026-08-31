from math import exp

import pytest

from pyoptionpricer.market import (
    CompoundingConvention,
    DayCountConvention,
    FlatYieldCurve,
    InterpolatedYieldCurve,
    InterpolationMethod,
    InvalidCurveError,
)


def test_interpolated_curve_returns_maturity_specific_zero_rate() -> None:
    curve = InterpolatedYieldCurve(
        maturities=(0.25, 1.0, 2.0),
        rates=(0.04, 0.05, 0.07),
    )

    assert curve.zero_rate(1.5) == pytest.approx(0.06)
    assert curve.interpolation_method is InterpolationMethod.LINEAR_ZERO_RATE


def test_curve_uses_flat_endpoint_extrapolation() -> None:
    curve = InterpolatedYieldCurve((0.25, 1.0), (0.04, 0.05))

    assert curve.zero_rate(0.0) == pytest.approx(0.04)
    assert curve.zero_rate(10.0) == pytest.approx(0.05)


def test_discount_factor_uses_continuous_compounding() -> None:
    curve = FlatYieldCurve(0.05)

    assert curve.discount_factor(2.0) == pytest.approx(exp(-0.05 * 2.0))
    assert curve.compounding_convention is CompoundingConvention.CONTINUOUS
    assert curve.day_count_convention is DayCountConvention.ACTUAL_365_FIXED


@pytest.mark.parametrize("maturity", [-0.01, float("nan"), float("inf"), True])
def test_curve_rejects_invalid_requested_maturity(maturity: float) -> None:
    with pytest.raises(InvalidCurveError, match="maturity"):
        FlatYieldCurve(0.05).zero_rate(maturity)


@pytest.mark.parametrize(
    ("maturities", "rates", "message"),
    [
        ((), (), "at least one pillar"),
        ((1.0,), (0.05, 0.06), "equal lengths"),
        ((1.0, 1.0), (0.05, 0.06), "strictly increasing"),
    ],
)
def test_interpolated_curve_rejects_invalid_pillars(
    maturities: tuple[float, ...], rates: tuple[float, ...], message: str
) -> None:
    with pytest.raises(InvalidCurveError, match=message):
        InterpolatedYieldCurve(maturities, rates)
