from datetime import UTC, date, datetime
from math import exp

import pytest

from pyoptionpricer import (
    AssetClass,
    BSMModelParameters,
    BSMPricingEngine,
    BarrierDirection,
    BarrierKnockType,
    BarrierMonitoringConvention,
    BarrierOptionContract,
    BarrierPricingDiagnostics,
    CRRModelParameters,
    CRRPricingEngine,
    DiagnosticCode,
    DiagnosticStatus,
    ExerciseStyle,
    OptionProduct,
    OptionType,
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


def market(spot: float = 100.0) -> MarketSnapshot:
    observed = VALUATION.replace(minute=59, hour=11)
    return MarketSnapshot(
        VALUATION,
        MarketObservation(spot, observed, "TEST", "spot"),
        OptionQuote(5.0, 6.0, 5.5, observed),
        FlatYieldCurve(0.05),
        ContinuousDividendYield(0.01),
        0.20,
    )


def barrier_request(
    direction: BarrierDirection,
    knock_type: BarrierKnockType,
    *,
    level: float,
    rebate: float = 0.0,
    option_type: OptionType = OptionType.CALL,
    spot: float = 100.0,
    steps: int = 200,
    bsm: bool = False,
) -> PricingRequest:
    contract = BarrierOptionContract(
        underlying="ACME",
        strike=100.0,
        expiry=EXPIRY,
        option_type=option_type,
        exercise_style=ExerciseStyle.EUROPEAN,
        asset_class=AssetClass.EQUITY,
        barrier_level=level,
        barrier_direction=direction,
        knock_type=knock_type,
        rebate=rebate,
    )
    parameters = BSMModelParameters() if bsm else CRRModelParameters(steps)
    return PricingRequest(contract, market(spot), parameters)


def vanilla_request(
    option_type: OptionType = OptionType.CALL, *, steps: int = 200
) -> PricingRequest:
    contract = VanillaOptionContract(
        "ACME",
        100.0,
        EXPIRY,
        option_type,
        ExerciseStyle.EUROPEAN,
        AssetClass.EQUITY,
    )
    return PricingRequest(contract, market(), CRRModelParameters(steps))


@pytest.mark.parametrize(
    ("direction", "level"),
    [(BarrierDirection.UP, 100.0), (BarrierDirection.DOWN, 100.0)],
)
def test_barrier_reached_immediately_applies_knock_terms(
    direction: BarrierDirection, level: float
) -> None:
    engine = CRRPricingEngine()
    knocked_out = engine.price(
        barrier_request(direction, BarrierKnockType.OUT, level=level, rebate=7.5)
    )
    knocked_in = engine.price(
        barrier_request(direction, BarrierKnockType.IN, level=level, rebate=7.5)
    )
    vanilla = engine.price(vanilla_request())

    assert knocked_out.price == 7.5
    assert knocked_in.price == pytest.approx(vanilla.price, abs=1e-12)
    assert knocked_out.greeks.delta == pytest.approx(0.0, abs=1e-12)
    assert knocked_out.greeks.gamma == pytest.approx(0.0, abs=1e-12)
    assert knocked_in.greeks == vanilla.greeks


@pytest.mark.parametrize(
    ("direction", "level"),
    [(BarrierDirection.UP, 1_000_000.0), (BarrierDirection.DOWN, 0.0001)],
)
def test_barrier_never_reached_preserves_out_and_extinguishes_in(
    direction: BarrierDirection, level: float
) -> None:
    engine = CRRPricingEngine()
    knocked_out = engine.price(
        barrier_request(direction, BarrierKnockType.OUT, level=level)
    )
    knocked_in = engine.price(
        barrier_request(direction, BarrierKnockType.IN, level=level)
    )
    vanilla = engine.price(vanilla_request())

    assert knocked_out.price == pytest.approx(vanilla.price, abs=1e-12)
    assert knocked_in.price == 0.0
    assert knocked_out.diagnostics.grid_alignment_warnings


@pytest.mark.parametrize("option_type", [OptionType.CALL, OptionType.PUT])
@pytest.mark.parametrize(
    ("direction", "level"),
    [(BarrierDirection.UP, 120.0), (BarrierDirection.DOWN, 80.0)],
)
def test_zero_rebate_knock_in_out_parity(
    option_type: OptionType, direction: BarrierDirection, level: float
) -> None:
    engine = CRRPricingEngine()
    knocked_in = engine.price(
        barrier_request(
            direction, BarrierKnockType.IN, level=level, option_type=option_type
        )
    )
    knocked_out = engine.price(
        barrier_request(
            direction, BarrierKnockType.OUT, level=level, option_type=option_type
        )
    )
    vanilla = engine.price(vanilla_request(option_type))

    assert knocked_in.price + knocked_out.price == pytest.approx(
        vanilla.price, abs=1e-12
    )


def test_rebate_and_monitoring_assumptions_are_reported() -> None:
    result = CRRPricingEngine().price(
        barrier_request(
            BarrierDirection.UP,
            BarrierKnockType.OUT,
            level=101.0,
            rebate=4.0,
            steps=100,
        )
    )

    assert isinstance(result.diagnostics, BarrierPricingDiagnostics)
    assert result.diagnostics.barrier_level == 101.0
    assert result.diagnostics.barrier_direction is BarrierDirection.UP
    assert result.diagnostics.knock_type is BarrierKnockType.OUT
    assert result.diagnostics.barrier_type == "UP_AND_OUT"
    assert (
        result.diagnostics.monitoring_convention
        is BarrierMonitoringConvention.DISCRETE_NODES
    )
    assert result.diagnostics.rebate == 4.0
    assert result.diagnostics.tree_steps == 100
    assert result.diagnostics.grid_alignment_warnings
    assert result.diagnostics.rebate_timing == "PAID_AT_FIRST_MONITORED_BREACH"


def test_unactivated_knock_in_rebate_is_paid_at_expiry() -> None:
    result = CRRPricingEngine().price(
        barrier_request(
            BarrierDirection.UP,
            BarrierKnockType.IN,
            level=1_000_000.0,
            rebate=8.0,
        )
    )

    assert result.price == pytest.approx(8.0 * exp(-0.05), abs=1e-12)
    assert result.diagnostics.rebate_timing == "PAID_AT_EXPIRY_IF_NOT_ACTIVATED"


def test_bsm_rejects_barrier_contract_explicitly() -> None:
    pricing_request = barrier_request(
        BarrierDirection.UP,
        BarrierKnockType.OUT,
        level=120.0,
        bsm=True,
    )

    with pytest.raises(UnsupportedInstrumentModelCombinationError) as raised:
        BSMPricingEngine().price(pricing_request)

    assert raised.value.product.value == "BARRIER"


def test_crr_declares_barrier_and_path_dependent_capability() -> None:
    capabilities = CRRPricingEngine.capabilities

    assert capabilities.supports_path_dependency is True
    assert OptionProduct.BARRIER in capabilities.products


def test_barrier_result_integrates_with_model_neutral_diagnostics() -> None:
    pricing_request = barrier_request(
        BarrierDirection.DOWN,
        BarrierKnockType.OUT,
        level=80.0,
    )
    engine = CRRPricingEngine()

    report = diagnose_pricing_result(
        pricing_request, engine.price(pricing_request)
    )

    assert report.get(DiagnosticCode.RISK_NEUTRAL_PROBABILITY).status is (
        DiagnosticStatus.PASS
    )
    assert report.get(DiagnosticCode.NO_ARBITRAGE).status is DiagnosticStatus.PASS
