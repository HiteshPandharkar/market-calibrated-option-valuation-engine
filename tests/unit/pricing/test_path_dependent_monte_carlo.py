from datetime import UTC, date, datetime, timedelta

import pytest

from pyoptionpricer import (
    AssetClass,
    AsianMonteCarloPricingDiagnostics,
    AsianOptionContract,
    BSMModelParameters,
    CRRModelParameters,
    ExerciseStyle,
    LookbackMonteCarloPricingDiagnostics,
    LookbackOptionContract,
    MonteCarloModelParameters,
    OptionType,
    PricingEngineRegistry,
    PricingError,
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


VALUATION = datetime(2026, 9, 2, 12, tzinfo=UTC)
EXPIRY = date(2027, 9, 2)


def market() -> MarketSnapshot:
    observed = VALUATION.replace(hour=11, minute=59)
    return MarketSnapshot(
        VALUATION,
        MarketObservation(100.0, observed, "TEST", "spot"),
        OptionQuote(8.0, 9.0, 8.5, observed),
        FlatYieldCurve(0.05),
        ContinuousDividendYield(0.02),
        0.20,
    )


def common_terms(option_type: OptionType = OptionType.CALL) -> dict[str, object]:
    return {
        "underlying": "ACME",
        "strike": 100.0,
        "expiry": EXPIRY,
        "option_type": option_type,
        "exercise_style": ExerciseStyle.EUROPEAN,
        "asset_class": AssetClass.EQUITY,
    }


def parameters(paths: int = 2_000) -> MonteCarloModelParameters:
    return MonteCarloModelParameters(
        number_of_paths=paths, time_steps=5, random_seed=83
    )


def aligned_schedule() -> tuple[date, ...]:
    return tuple(VALUATION.date() + timedelta(days=73 * index) for index in range(1, 6))


@pytest.mark.parametrize("option_type", [OptionType.CALL, OptionType.PUT])
def test_seeded_asian_pricing_is_reproducible_with_required_diagnostics(
    option_type: OptionType,
) -> None:
    contract = AsianOptionContract(
        **common_terms(option_type), observation_schedule=aligned_schedule()
    )
    request = PricingRequest(contract, market(), parameters())
    registry = PricingEngineRegistry()

    first = registry.price(request)
    second = PricingEngineRegistry().price(request)

    assert first == second
    assert first.price >= 0
    assert isinstance(first.diagnostics, AsianMonteCarloPricingDiagnostics)
    assert first.diagnostics.observation_count == 5
    assert first.diagnostics.standard_error > 0
    assert first.diagnostics.seed == 83
    assert first.diagnostics.random_seed == 83


def test_one_observation_asian_matches_vanilla_for_identical_paths() -> None:
    asian = AsianOptionContract(
        **common_terms(), observation_schedule=(EXPIRY,)
    )
    vanilla = VanillaOptionContract(**common_terms())
    registry = PricingEngineRegistry()

    asian_result = registry.price(PricingRequest(asian, market(), parameters()))
    vanilla_result = registry.price(PricingRequest(vanilla, market(), parameters()))

    assert asian_result.price == vanilla_result.price


@pytest.mark.parametrize("option_type", [OptionType.CALL, OptionType.PUT])
def test_seeded_lookback_pricing_reports_uncertainty(
    option_type: OptionType,
) -> None:
    contract = LookbackOptionContract(
        **common_terms(option_type), monitoring_schedule=aligned_schedule()
    )
    request = PricingRequest(contract, market(), parameters())

    first = PricingEngineRegistry().price(request)
    second = PricingEngineRegistry().price(request)

    assert first == second
    assert first.price >= 0
    assert isinstance(first.diagnostics, LookbackMonteCarloPricingDiagnostics)
    assert first.diagnostics.monitoring_count == 5
    assert first.diagnostics.standard_error > 0


@pytest.mark.parametrize("product", ["asian", "lookback"])
def test_more_paths_reduce_path_dependent_standard_error(product: str) -> None:
    if product == "asian":
        contract = AsianOptionContract(
            **common_terms(), observation_schedule=aligned_schedule()
        )
    else:
        contract = LookbackOptionContract(
            **common_terms(), monitoring_schedule=aligned_schedule()
        )

    small = PricingEngineRegistry().price(
        PricingRequest(contract, market(), parameters(1_000))
    )
    large = PricingEngineRegistry().price(
        PricingRequest(contract, market(), parameters(8_000))
    )

    assert large.diagnostics.standard_error < small.diagnostics.standard_error


def test_schedule_must_align_exactly_with_monte_carlo_grid() -> None:
    contract = AsianOptionContract(
        **common_terms(),
        observation_schedule=(VALUATION.date() + timedelta(days=1), EXPIRY),
    )

    with pytest.raises(PricingError, match="align exactly"):
        PricingEngineRegistry().price(
            PricingRequest(contract, market(), parameters())
        )


@pytest.mark.parametrize("model_parameters", [BSMModelParameters(), CRRModelParameters()])
@pytest.mark.parametrize("contract_type,schedule_name", [
    (AsianOptionContract, "observation_schedule"),
    (LookbackOptionContract, "monitoring_schedule"),
])
def test_unsupported_engines_reject_path_dependent_products(
    model_parameters: BSMModelParameters | CRRModelParameters,
    contract_type: type[AsianOptionContract] | type[LookbackOptionContract],
    schedule_name: str,
) -> None:
    contract = contract_type(
        **common_terms(), **{schedule_name: (EXPIRY,)}
    )

    with pytest.raises(UnsupportedInstrumentModelCombinationError):
        PricingEngineRegistry().price(
            PricingRequest(contract, market(), model_parameters)
        )
