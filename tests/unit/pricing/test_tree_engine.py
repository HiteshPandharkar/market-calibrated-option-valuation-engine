from datetime import UTC, date, datetime, timedelta
from math import erf, exp, log, pi, sqrt

import pytest

from pyoptionpricer import (
    AssetClass,
    BermudanExercise,
    CRRModelParameters,
    CRRPricingEngine,
    Currency,
    ExerciseStyle,
    InvalidPricingRequestError,
    OptionType,
    PricingError,
    PricingResult,
    PricingRequest,
    VanillaOptionContract,
)
from pyoptionpricer.market import (
    ContinuousDividendYield,
    FlatYieldCurve,
    MarketObservation,
    MarketSnapshot,
    OptionQuote,
)


VALUATION = datetime(2026, 8, 30, 12, 0, tzinfo=UTC)
EXPIRY = date(2027, 8, 30)


def request(
    option_type: OptionType = OptionType.CALL,
    exercise_style: ExerciseStyle = ExerciseStyle.EUROPEAN,
    *,
    spot: float = 100.0,
    strike: float = 100.0,
    rate: float = 0.05,
    dividend: float = 0.0,
    volatility: object = 0.20,
    steps: int = 500,
    expiry: date = EXPIRY,
    exercise_schedule: BermudanExercise | None = None,
) -> PricingRequest:
    contract = VanillaOptionContract(
        "ACME",
        strike,
        expiry,
        option_type,
        exercise_style,
        AssetClass.EQUITY,
        currency=Currency.USD,
        exercise_schedule=exercise_schedule,
    )
    timestamp = datetime(2026, 8, 30, 11, 59, tzinfo=UTC)
    snapshot = MarketSnapshot(
        valuation_datetime=VALUATION,
        spot=MarketObservation(spot, timestamp, "CSV", "price", "spots.csv"),
        option_quote=OptionQuote(9.0, 10.0, 9.5, timestamp),
        yield_curve=FlatYieldCurve(rate),
        dividend_data=ContinuousDividendYield(dividend),
        volatility_input=volatility,
    )
    return PricingRequest(contract, snapshot, CRRModelParameters(steps))


def normal_cdf(value: float) -> float:
    return 0.5 * (1.0 + erf(value / sqrt(2.0)))


def black_scholes_price(option_type: OptionType) -> float:
    d1 = (log(100.0 / 100.0) + (0.05 + 0.5 * 0.20**2)) / 0.20
    d2 = d1 - 0.20
    if option_type is OptionType.CALL:
        return 100.0 * normal_cdf(d1) - 100.0 * exp(-0.05) * normal_cdf(d2)
    return 100.0 * exp(-0.05) * normal_cdf(-d2) - 100.0 * normal_cdf(-d1)


def black_scholes_greeks(option_type: OptionType) -> tuple[float, float, float]:
    d1 = (0.05 + 0.5 * 0.20**2) / 0.20
    d2 = d1 - 0.20
    density = exp(-0.5 * d1**2) / sqrt(2.0 * pi)
    delta = normal_cdf(d1)
    theta = -100.0 * density * 0.20 / 2.0
    if option_type is OptionType.CALL:
        theta -= 0.05 * 100.0 * exp(-0.05) * normal_cdf(d2)
    else:
        delta -= 1.0
        theta += 0.05 * 100.0 * exp(-0.05) * normal_cdf(-d2)
    gamma = density / (100.0 * 0.20)
    return delta, gamma, theta


@pytest.mark.parametrize("option_type", [OptionType.CALL, OptionType.PUT])
def test_european_crr_converges_to_black_scholes(option_type: OptionType) -> None:
    result = CRRPricingEngine().price(request(option_type, steps=1000))

    assert isinstance(result, PricingResult)
    assert result.price == pytest.approx(black_scholes_price(option_type), abs=0.01)
    assert result.model_name == "CRR"
    assert result.currency is Currency.USD
    assert result.diagnostics.early_exercise_nodes == 0


@pytest.mark.parametrize("option_type", [OptionType.CALL, OptionType.PUT])
def test_tree_greeks_converge_to_black_scholes(option_type: OptionType) -> None:
    result = CRRPricingEngine().price(request(option_type, steps=1000))
    expected_delta, expected_gamma, expected_theta = black_scholes_greeks(option_type)

    assert result.greeks.delta == pytest.approx(expected_delta, abs=0.001)
    assert result.greeks.gamma == pytest.approx(expected_gamma, abs=0.0001)
    assert result.greeks.theta == pytest.approx(expected_theta, abs=0.02)


def test_pricing_rejects_tree_too_small_for_stable_greeks() -> None:
    with pytest.raises(PricingError, match="at least two CRR steps"):
        CRRPricingEngine().price(request(steps=1))


def test_american_put_includes_early_exercise() -> None:
    engine = CRRPricingEngine()
    european = engine.price(
        request(OptionType.PUT, ExerciseStyle.EUROPEAN, spot=80.0, steps=200)
    )
    american = engine.price(
        request(OptionType.PUT, ExerciseStyle.AMERICAN, spot=80.0, steps=200)
    )

    assert american.price > european.price
    assert american.diagnostics.early_exercise_nodes > 0


def test_non_dividend_american_call_matches_european_call() -> None:
    engine = CRRPricingEngine()
    european = engine.price(request(steps=200))
    american = engine.price(
        request(exercise_style=ExerciseStyle.AMERICAN, steps=200)
    )

    assert american.price == pytest.approx(european.price)
    assert american.diagnostics.early_exercise_nodes == 0


def test_bermudan_put_is_bounded_by_european_and_american_prices() -> None:
    schedule = BermudanExercise(
        tuple(
            VALUATION.date() + timedelta(days=offset)
            for offset in (91, 182, 273, 365)
        )
    )
    engine = CRRPricingEngine()

    european = engine.price(
        request(OptionType.PUT, ExerciseStyle.EUROPEAN, spot=80.0, steps=365)
    )
    bermudan = engine.price(
        request(
            OptionType.PUT,
            ExerciseStyle.BERMUDAN,
            spot=80.0,
            steps=365,
            exercise_schedule=schedule,
        )
    )
    american = engine.price(
        request(OptionType.PUT, ExerciseStyle.AMERICAN, spot=80.0, steps=365)
    )

    assert european.price < bermudan.price < american.price
    assert bermudan.diagnostics.early_exercise_nodes > 0


def test_bermudan_valuation_date_exercise_maps_to_root_node() -> None:
    schedule = BermudanExercise((VALUATION.date(), EXPIRY))

    result = CRRPricingEngine().price(
        request(
            OptionType.PUT,
            ExerciseStyle.BERMUDAN,
            spot=20.0,
            steps=365,
            exercise_schedule=schedule,
        )
    )

    assert result.price == pytest.approx(80.0)
    assert result.diagnostics.early_exercise_nodes == 1


def test_bermudan_rejects_exercise_date_not_exactly_on_tree_grid() -> None:
    schedule = BermudanExercise(
        (VALUATION.date() + timedelta(days=90), EXPIRY)
    )

    with pytest.raises(PricingError, match="does not align exactly"):
        CRRPricingEngine().price(
            request(
                OptionType.PUT,
                ExerciseStyle.BERMUDAN,
                steps=100,
                exercise_schedule=schedule,
            )
        )


def test_pricing_request_resolves_traceable_inputs() -> None:
    volatility = MarketObservation(0.20, VALUATION, "UPSTOX", "estimated_volatility")
    pricing_request = request(volatility=volatility)

    assert pricing_request.inputs.spot.value == 100.0
    assert pricing_request.inputs.spot.source == "CSV"
    assert pricing_request.inputs.strike.source == "option_contract"
    assert pricing_request.inputs.maturity.value == pytest.approx(1.0)
    assert pricing_request.inputs.risk_free_rate.value == 0.05
    assert pricing_request.inputs.dividend_yield.value == 0.0
    assert pricing_request.inputs.volatility.source == "UPSTOX"


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"expiry": date(2026, 8, 30)}, "expire"),
        ({"volatility": None}, "volatility"),
        ({"volatility": 0.0}, "volatility"),
        (
            {
                "volatility": MarketObservation(
                    "invalid", VALUATION, "TEST", "volatility"
                )
            },
            "volatility",
        ),
    ],
)
def test_pricing_request_rejects_incomplete_or_invalid_inputs(
    overrides: dict[str, object], message: str
) -> None:
    with pytest.raises(InvalidPricingRequestError, match=message):
        request(**overrides)  # type: ignore[arg-type]
