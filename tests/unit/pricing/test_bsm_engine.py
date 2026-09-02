from datetime import UTC, date, datetime
from math import exp

import pytest

from pyoptionpricer import (
    AssetClass,
    BermudanExercise,
    BSMModelParameters,
    BSMPricingDiagnostics,
    BSMPricingEngine,
    CRRModelParameters,
    CRRPricingEngine,
    Currency,
    DiagnosticCode,
    DiagnosticStatus,
    ExerciseStyle,
    OptionType,
    PricingEngineRegistry,
    PricingError,
    InvalidPricingRequestError,
    PricingModel,
    PricingRequest,
    UnsupportedInstrumentModelCombinationError,
    VanillaOptionContract,
    diagnose_pricing_result,
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
    option_type: OptionType = OptionType.CALL,
    *,
    exercise_style: ExerciseStyle = ExerciseStyle.EUROPEAN,
    spot: float = 100.0,
    strike: float = 100.0,
    rate: float = 0.05,
    dividend: float = 0.0,
    volatility: float = 0.20,
    expiry: date = EXPIRY,
    parameters: BSMModelParameters | CRRModelParameters | None = None,
) -> PricingRequest:
    contract = VanillaOptionContract(
        "ACME",
        strike,
        expiry,
        option_type,
        exercise_style,
        AssetClass.EQUITY,
        currency=Currency.USD,
    )
    observed = VALUATION.replace(minute=59, hour=11)
    snapshot = MarketSnapshot(
        VALUATION,
        MarketObservation(spot, observed, "TEST", "spot"),
        OptionQuote(5.0, 6.0, 5.5, observed),
        FlatYieldCurve(rate),
        ContinuousDividendYield(dividend),
        volatility,
    )
    return PricingRequest(contract, snapshot, parameters or BSMModelParameters())


@pytest.mark.parametrize(
    ("option_type", "expected_price"),
    [
        (OptionType.CALL, 10.450583572185565),
        (OptionType.PUT, 5.573526022256971),
    ],
)
def test_bsm_matches_independent_reference_prices(
    option_type: OptionType, expected_price: float
) -> None:
    result = BSMPricingEngine().price(request(option_type))

    assert result.price == pytest.approx(expected_price, abs=1e-12)
    assert result.model is PricingModel.BLACK_SCHOLES_MERTON
    assert result.model_name == PricingModel.BLACK_SCHOLES_MERTON.value
    assert isinstance(result.diagnostics, BSMPricingDiagnostics)
    assert result.diagnostics.calculation_mode == "ANALYTICAL"


def test_bsm_dividend_yield_price_and_analytical_greeks() -> None:
    result = BSMPricingEngine().price(request(dividend=0.02))

    assert result.price == pytest.approx(9.227005508154036, abs=1e-12)
    assert result.greeks.delta == pytest.approx(0.586851146134764, abs=1e-12)
    assert result.greeks.gamma == pytest.approx(0.0189505787550087, abs=1e-12)
    assert result.greeks.theta == pytest.approx(-5.08931891399833, abs=1e-12)
    assert result.greeks.vega == pytest.approx(37.9011575100174, abs=1e-12)
    assert result.greeks.rho == pytest.approx(49.4581091053224, abs=1e-12)


def test_bsm_put_call_parity_with_continuous_dividend_yield() -> None:
    engine = BSMPricingEngine()
    call = engine.price(request(OptionType.CALL, dividend=0.02))
    put = engine.price(request(OptionType.PUT, dividend=0.02))

    parity = 100.0 * exp(-0.02) - 100.0 * exp(-0.05)
    assert call.price - put.price == pytest.approx(parity, abs=1e-12)


def test_bsm_result_has_model_neutral_no_arbitrage_diagnostics() -> None:
    pricing_request = request(dividend=0.02)
    result = BSMPricingEngine().price(pricing_request)

    report = diagnose_pricing_result(pricing_request, result)

    assert report.overall_status is DiagnosticStatus.PASS
    assert report.get(DiagnosticCode.NO_ARBITRAGE).status is DiagnosticStatus.PASS


def test_bsm_uses_explicit_deterministic_limit_for_near_zero_volatility() -> None:
    parameters = BSMModelParameters(near_zero_volatility=1e-6)
    result = BSMPricingEngine().price(
        request(volatility=1e-8, parameters=parameters)
    )

    expected = 100.0 - 100.0 * exp(-0.05)
    assert result.price == pytest.approx(expected, abs=1e-12)
    assert result.greeks.gamma == 0.0
    assert result.greeks.vega == 0.0
    assert result.diagnostics.calculation_mode == "DETERMINISTIC_LIMIT"
    assert result.diagnostics.d1 is None


def test_bsm_uses_explicit_deterministic_limit_for_near_zero_maturity() -> None:
    parameters = BSMModelParameters(near_zero_maturity=0.01)
    result = BSMPricingEngine().price(
        request(expiry=date(2026, 9, 2), parameters=parameters)
    )

    expected = 100.0 - 100.0 * exp(-0.05 / 365.0)
    assert result.price == pytest.approx(expected, abs=1e-12)
    assert result.diagnostics.calculation_mode == "DETERMINISTIC_LIMIT"


@pytest.mark.parametrize(
    "overrides",
    [
        {"expiry": date(2026, 9, 1)},
        {"volatility": 0.0},
    ],
)
def test_bsm_request_rejects_zero_maturity_or_volatility(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(InvalidPricingRequestError):
        request(**overrides)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("spot", "option_type"),
    [(1e-300, OptionType.PUT), (1e300, OptionType.CALL)],
)
def test_bsm_handles_extreme_moneyness(spot: float, option_type: OptionType) -> None:
    result = BSMPricingEngine().price(request(option_type, spot=spot))

    assert result.price >= 0.0


def test_bsm_rejects_rate_outside_numerically_supported_range() -> None:
    with pytest.raises(PricingError, match="risk-free rate"):
        BSMPricingEngine().price(request(rate=-1000.0))


def test_registry_rejects_american_vanilla_for_bsm() -> None:
    pricing_request = request(exercise_style=ExerciseStyle.AMERICAN)

    with pytest.raises(UnsupportedInstrumentModelCombinationError) as raised:
        PricingEngineRegistry().price(pricing_request)

    assert raised.value.model is PricingModel.BLACK_SCHOLES_MERTON
    assert raised.value.exercise_style is ExerciseStyle.AMERICAN


def test_bsm_rejects_bermudan_vanilla_explicitly() -> None:
    base_request = request()
    contract = VanillaOptionContract(
        "ACME",
        100.0,
        EXPIRY,
        OptionType.PUT,
        ExerciseStyle.BERMUDAN,
        AssetClass.EQUITY,
        exercise_schedule=BermudanExercise((EXPIRY,)),
    )
    pricing_request = PricingRequest(
        contract, base_request.market, BSMModelParameters()
    )

    with pytest.raises(UnsupportedInstrumentModelCombinationError) as raised:
        BSMPricingEngine().price(pricing_request)

    assert raised.value.model is PricingModel.BLACK_SCHOLES_MERTON
    assert raised.value.exercise_style is ExerciseStyle.BERMUDAN


@pytest.mark.parametrize("option_type", [OptionType.CALL, OptionType.PUT])
def test_crr_converges_to_bsm_under_matching_assumptions(
    option_type: OptionType,
) -> None:
    bsm = BSMPricingEngine().price(request(option_type, dividend=0.02))
    crr = CRRPricingEngine().price(
        request(
            option_type,
            dividend=0.02,
            parameters=CRRModelParameters(steps=2000),
        )
    )

    # A 2,000-step CRR tree is within one cent of the analytical value here.
    assert crr.price == pytest.approx(bsm.price, abs=0.01)
