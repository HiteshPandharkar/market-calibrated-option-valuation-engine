from datetime import UTC, date, datetime

import pytest

from pyoptionpricer import (
    AssetClass,
    BSMModelParameters,
    BSMPricingEngine,
    ExerciseStyle,
    MonteCarloModelParameters,
    MonteCarloPricingDiagnostics,
    MonteCarloPricingEngine,
    OptionType,
    PricingEngineRegistry,
    PricingModel,
    PricingRequest,
    UnsupportedInstrumentModelCombinationError,
    VanillaOptionContract,
)
from pyoptionpricer.market import (
    ContinuousDividendYield,
    FlatYieldCurve,
    MarketObservation,
    MarketSnapshot,
    OptionQuote,
)


VALUATION = datetime(2026, 9, 1, 12, tzinfo=UTC)


def request(
    parameters: MonteCarloModelParameters | BSMModelParameters,
    *,
    exercise_style: ExerciseStyle = ExerciseStyle.EUROPEAN,
) -> PricingRequest:
    observed = VALUATION.replace(hour=11, minute=59)
    contract = VanillaOptionContract(
        "ACME",
        100.0,
        date(2027, 9, 1),
        OptionType.CALL,
        exercise_style,
        AssetClass.EQUITY,
    )
    market = MarketSnapshot(
        VALUATION,
        MarketObservation(100.0, observed, "TEST", "spot"),
        OptionQuote(9.0, 10.0, 9.5, observed),
        FlatYieldCurve(0.05),
        ContinuousDividendYield(0.02),
        0.20,
    )
    return PricingRequest(contract, market, parameters)


def test_seeded_monte_carlo_result_is_reproducible_with_statistics() -> None:
    parameters = MonteCarloModelParameters(
        number_of_paths=2_000,
        time_steps=12,
        random_seed=42,
        antithetic_variates=True,
        confidence_level=0.99,
    )

    first = MonteCarloPricingEngine().price(request(parameters))
    second = MonteCarloPricingEngine().price(request(parameters))

    assert first == second
    assert first.model is PricingModel.MONTE_CARLO
    assert isinstance(first.diagnostics, MonteCarloPricingDiagnostics)
    assert first.diagnostics.estimated_price == first.price
    assert first.diagnostics.standard_error > 0
    assert first.diagnostics.confidence_interval[0] < first.price
    assert first.diagnostics.confidence_interval[1] > first.price
    assert first.diagnostics.number_of_paths == 2_000
    assert first.diagnostics.time_steps == 12
    assert first.diagnostics.seed == 42
    assert first.diagnostics.variance_reduction_method == "ANTITHETIC_VARIATES"
    assert first.diagnostics.confidence_level == 0.99


def test_monte_carlo_european_price_agrees_with_bsm_statistically() -> None:
    monte_carlo = MonteCarloPricingEngine().price(
        request(
            MonteCarloModelParameters(
                number_of_paths=20_000,
                time_steps=16,
                random_seed=2027,
                antithetic_variates=True,
            )
        )
    )
    analytical = BSMPricingEngine().price(request(BSMModelParameters()))
    diagnostics = monte_carlo.diagnostics
    assert isinstance(diagnostics, MonteCarloPricingDiagnostics)

    assert abs(monte_carlo.price - analytical.price) <= 4.0 * diagnostics.standard_error
    assert monte_carlo.greeks.delta > 0


def test_more_paths_reduce_standard_error_for_fixed_seeded_scenario() -> None:
    small = MonteCarloPricingEngine().price(
        request(
            MonteCarloModelParameters(
                number_of_paths=1_000, time_steps=4, random_seed=81
            )
        )
    )
    large = MonteCarloPricingEngine().price(
        request(
            MonteCarloModelParameters(
                number_of_paths=8_000, time_steps=4, random_seed=81
            )
        )
    )
    assert isinstance(small.diagnostics, MonteCarloPricingDiagnostics)
    assert isinstance(large.diagnostics, MonteCarloPricingDiagnostics)

    assert large.diagnostics.standard_error < small.diagnostics.standard_error


def test_registry_routes_monte_carlo_and_rejects_early_exercise() -> None:
    registry = PricingEngineRegistry()
    parameters = MonteCarloModelParameters(number_of_paths=100, time_steps=2)

    assert isinstance(registry.get(PricingModel.MONTE_CARLO), MonteCarloPricingEngine)
    with pytest.raises(UnsupportedInstrumentModelCombinationError):
        registry.price(request(parameters, exercise_style=ExerciseStyle.AMERICAN))
