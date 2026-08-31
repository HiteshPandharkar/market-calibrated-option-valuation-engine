from dataclasses import replace
from datetime import UTC, date, datetime

import pytest

from pyoptionpricer import (
    AssetClass,
    CRRImpliedVolatilitySolver,
    CRRModelParameters,
    CRRPricingEngine,
    ExerciseStyle,
    ImpliedVolatilityConfig,
    ImpliedVolatilityConvergenceError,
    ImpliedVolatilityError,
    OptionContract,
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


VALUATION = datetime(2026, 8, 30, 12, tzinfo=UTC)
TIMESTAMP = datetime(2026, 8, 30, 11, 59, tzinfo=UTC)


def make_request(
    *,
    volatility: float = 0.20,
    quote: OptionQuote | None = None,
    source: str = "CSV",
) -> PricingRequest:
    contract = OptionContract(
        "ACME",
        100.0,
        date(2027, 8, 30),
        OptionType.CALL,
        ExerciseStyle.EUROPEAN,
        AssetClass.EQUITY,
    )
    snapshot = MarketSnapshot(
        VALUATION,
        MarketObservation(100.0, TIMESTAMP, source, "last_price"),
        quote or OptionQuote(9.0, 11.0, 10.0, TIMESTAMP, source=source),
        FlatYieldCurve(0.05),
        ContinuousDividendYield(0.01),
        volatility,
    )
    return PricingRequest(contract, snapshot, CRRModelParameters(200))


def synthetic_request(volatility: float, *, source: str = "CSV") -> PricingRequest:
    seed = make_request(volatility=volatility, source=source)
    market_price = CRRPricingEngine().price(seed).price
    quote = OptionQuote(
        market_price - 0.01,
        market_price + 0.01,
        market_price,
        TIMESTAMP,
        source=source,
    )
    return replace(seed, market=replace(seed.market, option_quote=quote))


@pytest.mark.parametrize("source", ["CSV", "UPSTOX"])
def test_recovers_known_synthetic_iv_from_canonical_quote(source: str) -> None:
    request = synthetic_request(0.27, source=source)

    result = CRRImpliedVolatilitySolver().solve(request)

    assert result.implied_volatility == pytest.approx(0.27, abs=1e-6)
    assert result.model_price == pytest.approx(result.market_midpoint, abs=1e-6)
    assert abs(result.pricing_residual) <= result.tolerance
    assert result.iterations > 0
    assert result.pricing_result.inputs.volatility.value == pytest.approx(
        result.implied_volatility
    )


def test_custom_tolerance_controls_convergence() -> None:
    config = ImpliedVolatilityConfig(tolerance=0.01, max_iterations=20)

    result = CRRImpliedVolatilitySolver().solve(synthetic_request(0.24), config)

    assert abs(result.pricing_residual) <= 0.01
    assert result.tolerance == 0.01
    assert result.iterations <= 20


def test_calibration_rejects_quote_without_midpoint() -> None:
    quote = OptionQuote(None, 11.0, 10.0, TIMESTAMP)

    with pytest.raises(ImpliedVolatilityError, match="both bid and ask"):
        CRRImpliedVolatilitySolver().solve(make_request(quote=quote))


def test_calibration_rejects_market_price_outside_volatility_bracket() -> None:
    quote = OptionQuote(99.0, 99.0, 99.0, TIMESTAMP)

    with pytest.raises(ImpliedVolatilityError, match="not bracketed"):
        CRRImpliedVolatilitySolver().solve(make_request(quote=quote))


def test_non_convergence_exposes_iteration_count_and_residual() -> None:
    config = ImpliedVolatilityConfig(tolerance=1e-15, max_iterations=1)

    with pytest.raises(ImpliedVolatilityConvergenceError) as captured:
        CRRImpliedVolatilitySolver().solve(synthetic_request(0.27), config)

    assert captured.value.iterations == 1
    assert captured.value.pricing_residual != 0.0


@pytest.mark.parametrize(
    "kwargs",
    [
        {"lower_bound": 0.0},
        {"lower_bound": 0.5, "upper_bound": 0.5},
        {"tolerance": 0.0},
        {"max_iterations": 0},
        {"max_iterations": True},
    ],
)
def test_config_rejects_invalid_solver_controls(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        ImpliedVolatilityConfig(**kwargs)  # type: ignore[arg-type]
