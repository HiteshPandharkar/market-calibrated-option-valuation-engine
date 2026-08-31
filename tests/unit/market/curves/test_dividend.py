from math import exp

import pytest

from pyoptionpricer.market import ContinuousDividendYield, InvalidCurveError


def test_continuous_dividend_yield_supports_cost_of_carry_input() -> None:
    dividends = ContinuousDividendYield(0.012)

    assert dividends.continuous_rate(0.75) == pytest.approx(0.012)
    assert dividends.discount_factor(0.75) == pytest.approx(exp(-0.012 * 0.75))


@pytest.mark.parametrize("rate", [-0.01, float("nan"), float("inf"), True])
def test_continuous_dividend_yield_rejects_invalid_rate(rate: float) -> None:
    with pytest.raises(InvalidCurveError, match="rate|dividend yield"):
        ContinuousDividendYield(rate)


def test_continuous_dividend_yield_rejects_invalid_maturity() -> None:
    with pytest.raises(InvalidCurveError, match="maturity"):
        ContinuousDividendYield(0.01).continuous_rate(-1.0)
