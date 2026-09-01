from datetime import UTC, date, datetime
from math import erf, exp, log, sqrt

import pytest

from pyoptionpricer import (
    AssetClass,
    BSMModelParameters,
    BSMPricingEngine,
    CRRModelParameters,
    CRRPricingEngine,
    DigitalOptionContract,
    ExerciseStyle,
    OptionType,
    PricingRequest,
)
from pyoptionpricer.market import (
    ContinuousDividendYield,
    FlatYieldCurve,
    MarketObservation,
    MarketSnapshot,
    OptionQuote,
)


VALUATION = datetime(2026, 9, 1, 12, tzinfo=UTC)
EXPIRY = date(2027, 9, 1)


def request(
    option_type: OptionType,
    parameters: BSMModelParameters | CRRModelParameters,
    *,
    payout: float = 25.0,
    spot: float = 100.0,
    volatility: float = 0.20,
) -> PricingRequest:
    contract = DigitalOptionContract(
        underlying="ACME",
        strike=100.0,
        expiry=EXPIRY,
        option_type=option_type,
        exercise_style=ExerciseStyle.EUROPEAN,
        asset_class=AssetClass.EQUITY,
        cash_payout=payout,
    )
    observed = VALUATION.replace(minute=59, hour=11)
    snapshot = MarketSnapshot(
        VALUATION,
        MarketObservation(spot, observed, "TEST", "spot"),
        OptionQuote(10.0, 11.0, 10.5, observed),
        FlatYieldCurve(0.05),
        ContinuousDividendYield(0.02),
        volatility,
    )
    return PricingRequest(contract, snapshot, parameters)


def normal_cdf(value: float) -> float:
    return 0.5 * (1.0 + erf(value / sqrt(2.0)))


@pytest.mark.parametrize("option_type", [OptionType.CALL, OptionType.PUT])
def test_bsm_cash_digital_matches_independent_reference(
    option_type: OptionType,
) -> None:
    result = BSMPricingEngine().price(request(option_type, BSMModelParameters()))
    d2 = (log(1.0) + (0.05 - 0.02 - 0.5 * 0.20**2)) / 0.20
    probability = normal_cdf(d2 if option_type is OptionType.CALL else -d2)

    assert result.price == pytest.approx(25.0 * exp(-0.05) * probability, abs=1e-12)
    assert result.greeks.vega is not None
    assert result.greeks.rho is not None


def test_digital_call_and_put_sum_to_discounted_payout() -> None:
    engine = BSMPricingEngine()
    call = engine.price(request(OptionType.CALL, BSMModelParameters()))
    put = engine.price(request(OptionType.PUT, BSMModelParameters()))

    assert call.price + put.price == pytest.approx(25.0 * exp(-0.05), abs=1e-12)


def test_bsm_digital_strategy_uses_its_deterministic_limit() -> None:
    parameters = BSMModelParameters(near_zero_volatility=1e-6)
    result = BSMPricingEngine().price(
        request(
            OptionType.CALL,
            parameters,
            spot=110.0,
            volatility=1e-8,
        )
    )

    assert result.price == pytest.approx(25.0 * exp(-0.05), abs=1e-12)
    assert result.greeks.delta == 0.0
    assert result.diagnostics.calculation_mode == "DETERMINISTIC_LIMIT"


def test_bsm_digital_spot_greeks_match_finite_difference() -> None:
    engine = BSMPricingEngine()
    base = engine.price(request(OptionType.CALL, BSMModelParameters()))
    bump = 0.001
    down = engine.price(
        request(OptionType.CALL, BSMModelParameters(), spot=100.0 - bump)
    )
    up = engine.price(
        request(OptionType.CALL, BSMModelParameters(), spot=100.0 + bump)
    )

    finite_delta = (up.price - down.price) / (2.0 * bump)
    finite_gamma = (up.price - 2.0 * base.price + down.price) / bump**2
    assert base.greeks.delta == pytest.approx(finite_delta, abs=1e-8)
    assert base.greeks.gamma == pytest.approx(finite_gamma, abs=1e-8)


@pytest.mark.parametrize("option_type", [OptionType.CALL, OptionType.PUT])
def test_crr_cash_digital_converges_near_bsm_reference(option_type: OptionType) -> None:
    bsm = BSMPricingEngine().price(request(option_type, BSMModelParameters()))
    engine = CRRPricingEngine()
    coarse = engine.price(request(option_type, CRRModelParameters(steps=100)))
    fine = engine.price(request(option_type, CRRModelParameters(steps=2000)))

    # The discontinuity makes lattice convergence oscillatory around strike.
    assert abs(fine.price - bsm.price) < abs(coarse.price - bsm.price)
    assert fine.price == pytest.approx(bsm.price, abs=0.25)


def test_crr_exposes_strike_node_sensitivity_in_price_and_greeks() -> None:
    engine = CRRPricingEngine()
    below = engine.price(
        request(OptionType.CALL, CRRModelParameters(steps=100), spot=99.999999)
    )
    above = engine.price(
        request(OptionType.CALL, CRRModelParameters(steps=100), spot=100.000001)
    )

    assert below.price != above.price
    assert below.greeks != above.greeks
