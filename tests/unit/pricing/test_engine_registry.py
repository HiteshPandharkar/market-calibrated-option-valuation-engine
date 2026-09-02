from datetime import UTC, date, datetime

import pytest

from pyoptionpricer import (
    AssetClass,
    BSMPricingEngine,
    CRRModelParameters,
    CRRPricingEngine,
    EngineCapabilities,
    ExerciseStyle,
    ModelCapabilityValidator,
    ModelSelection,
    MonteCarloPricingEngine,
    OptionProduct,
    OptionType,
    PRICING_ENGINE_ROUTES,
    PricingEngineRegistry,
    PricingModel,
    PricingRequest,
    InvalidPricingRequestError,
    UnsupportedInstrumentModelCombinationError,
    UnsupportedModelError,
    VanillaOptionContract,
    build_available_pricing_engine,
)
from pyoptionpricer.market import (
    ContinuousDividendYield,
    FlatYieldCurve,
    MarketObservation,
    MarketSnapshot,
    OptionQuote,
)


def pricing_request(
    exercise_style: ExerciseStyle = ExerciseStyle.EUROPEAN,
) -> PricingRequest:
    valuation = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
    observed = datetime(2026, 9, 1, 11, 59, tzinfo=UTC)
    contract = VanillaOptionContract(
        underlying="ACME",
        strike=100.0,
        expiry=date(2027, 9, 1),
        option_type=OptionType.CALL,
        exercise_style=exercise_style,
        asset_class=AssetClass.EQUITY,
    )
    snapshot = MarketSnapshot(
        valuation_datetime=valuation,
        spot=MarketObservation(100.0, observed, "TEST", "spot"),
        option_quote=OptionQuote(9.0, 10.0, 9.5, observed),
        yield_curve=FlatYieldCurve(0.05),
        dividend_data=ContinuousDividendYield(0.0),
        volatility_input=0.2,
    )
    return PricingRequest(contract, snapshot, CRRModelParameters(steps=100))


def test_model_selection_is_derived_from_model_specific_configuration() -> None:
    request = pricing_request()

    assert request.model is PricingModel.CRR
    assert request.model_selection == ModelSelection(
        PricingModel.CRR, request.model_parameters
    )


def test_pricing_request_rejects_noncanonical_model_configuration() -> None:
    class InvalidConfiguration:
        model = "CRR"

    valid = pricing_request()

    with pytest.raises(InvalidPricingRequestError, match="must be a PricingModel"):
        PricingRequest(
            valid.instrument,
            valid.market,
            InvalidConfiguration(),  # type: ignore[arg-type]
        )


def test_registry_selects_crr_by_canonical_model_and_dispatches() -> None:
    registry = PricingEngineRegistry()
    request = pricing_request()

    assert registry.models == frozenset(
        {
            PricingModel.CRR,
            PricingModel.BLACK_SCHOLES_MERTON,
            PricingModel.MONTE_CARLO,
        }
    )
    assert isinstance(registry.get(PricingModel.CRR), CRRPricingEngine)
    result = registry.price(request)
    assert result.model is PricingModel.CRR
    assert result.model_name == PricingModel.CRR.value


def test_router_builds_only_the_model_selected_by_string_value() -> None:
    engine = build_available_pricing_engine(PricingModel.CRR.value)

    assert isinstance(engine, CRRPricingEngine)
    bsm_engine = build_available_pricing_engine(
        PricingModel.BLACK_SCHOLES_MERTON.value
    )
    assert isinstance(bsm_engine, BSMPricingEngine)
    assert isinstance(
        build_available_pricing_engine(PricingModel.MONTE_CARLO),
        MonteCarloPricingEngine,
    )


def test_registry_constructs_selected_engine_lazily(monkeypatch: pytest.MonkeyPatch) -> None:
    from pyoptionpricer.pricing import engine_registry

    calls: list[PricingModel | str] = []
    original_builder = engine_registry.build_available_pricing_engine

    def recording_builder(model: PricingModel | str) -> object:
        calls.append(model)
        return original_builder(model)

    monkeypatch.setattr(
        engine_registry, "build_available_pricing_engine", recording_builder
    )
    registry = PricingEngineRegistry()

    assert calls == []
    first = registry.get(PricingModel.CRR.value)
    second = registry.get(PricingModel.CRR)

    assert first is second
    assert calls == [PricingModel.CRR]


def test_engine_router_is_the_immutable_repository_catalogue() -> None:
    assert set(PRICING_ENGINE_ROUTES) == {
        PricingModel.CRR,
        PricingModel.BLACK_SCHOLES_MERTON,
        PricingModel.MONTE_CARLO,
    }
    assert PRICING_ENGINE_ROUTES[PricingModel.CRR] is CRRPricingEngine
    assert (
        PRICING_ENGINE_ROUTES[PricingModel.BLACK_SCHOLES_MERTON]
        is BSMPricingEngine
    )
    assert PRICING_ENGINE_ROUTES[PricingModel.MONTE_CARLO] is MonteCarloPricingEngine

    with pytest.raises(TypeError):
        PRICING_ENGINE_ROUTES[PricingModel.MONTE_CARLO] = (  # type: ignore[index]
            CRRPricingEngine
        )


def test_registry_fails_explicitly_when_selected_engine_is_unknown() -> None:
    registry = PricingEngineRegistry()

    with pytest.raises(UnsupportedModelError) as raised:
        registry.get("UNKNOWN")

    assert raised.value.model == "UNKNOWN"
    assert raised.value.available_models == frozenset(
        {
            PricingModel.CRR,
            PricingModel.BLACK_SCHOLES_MERTON,
            PricingModel.MONTE_CARLO,
        }
    )


def test_registry_does_not_expose_runtime_engine_registration() -> None:
    registry = PricingEngineRegistry()

    assert not hasattr(registry, "register")
    with pytest.raises(TypeError):
        PricingEngineRegistry((CRRPricingEngine(),))  # type: ignore[call-arg]

    class ExternalRegistry(PricingEngineRegistry):  # type: ignore[misc]
        pass

    with pytest.raises(TypeError, match="cannot be subclassed"):
        ExternalRegistry()


@pytest.mark.parametrize(
    "exercise_style",
    [
        ExerciseStyle.EUROPEAN,
        ExerciseStyle.AMERICAN,
        ExerciseStyle.BERMUDAN,
    ],
)
def test_crr_capabilities_accept_supported_vanilla_styles(
    exercise_style: ExerciseStyle,
) -> None:
    engine = CRRPricingEngine()

    ModelCapabilityValidator().validate(
        engine.model,
        engine.capabilities,
        OptionProduct.VANILLA,
        exercise_style,
    )


def test_capability_validator_rejects_asian_with_crr_structurally() -> None:
    engine = CRRPricingEngine()

    with pytest.raises(UnsupportedInstrumentModelCombinationError) as raised:
        ModelCapabilityValidator().validate(
            engine.model,
            engine.capabilities,
            OptionProduct.ASIAN,
            ExerciseStyle.EUROPEAN,
        )

    assert raised.value.model is PricingModel.CRR
    assert raised.value.product is OptionProduct.ASIAN
    assert raised.value.exercise_style is ExerciseStyle.EUROPEAN


def test_capability_metadata_requires_explicit_supported_sets() -> None:
    with pytest.raises(ValueError, match="products"):
        EngineCapabilities(
            products=frozenset(),
            exercise_styles=frozenset({ExerciseStyle.EUROPEAN}),
            supports_path_dependency=False,
            supports_early_exercise=False,
        )
