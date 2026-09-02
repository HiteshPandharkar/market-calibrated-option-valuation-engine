from datetime import date

import pytest

from pyoptionpricer import (
    AssetClass,
    BarrierDirection,
    BarrierKnockType,
    BarrierMonitoringConvention,
    BarrierOptionContract,
    ExerciseStyle,
    InvalidContractError,
    OptionProduct,
    OptionType,
    VanillaPayoff,
)


def make_contract(**overrides: object) -> BarrierOptionContract:
    terms: dict[str, object] = {
        "underlying": "ACME",
        "strike": 100.0,
        "expiry": date(2027, 9, 1),
        "option_type": OptionType.CALL,
        "exercise_style": ExerciseStyle.EUROPEAN,
        "asset_class": AssetClass.EQUITY,
        "barrier_level": 120.0,
        "barrier_direction": BarrierDirection.UP,
        "knock_type": BarrierKnockType.OUT,
    }
    terms.update(overrides)
    return BarrierOptionContract(**terms)  # type: ignore[arg-type]


@pytest.mark.parametrize("direction", list(BarrierDirection))
@pytest.mark.parametrize("knock_type", list(BarrierKnockType))
def test_contract_canonically_represents_all_four_barrier_types(
    direction: BarrierDirection, knock_type: BarrierKnockType
) -> None:
    contract = make_contract(
        barrier_direction=direction,
        knock_type=knock_type,
    )

    assert contract.product is OptionProduct.BARRIER
    assert contract.payoff == VanillaPayoff(OptionType.CALL, 100.0)
    assert contract.monitoring_convention is BarrierMonitoringConvention.DISCRETE_NODES
    assert contract.rebate == 0.0


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("barrier_level", 0.0, "barrier_level"),
        ("barrier_level", float("nan"), "barrier_level"),
        ("barrier_direction", "UP", "barrier_direction"),
        ("knock_type", "OUT", "knock_type"),
        ("rebate", -1.0, "rebate"),
        ("monitoring_convention", "CONTINUOUS", "monitoring_convention"),
    ],
)
def test_contract_rejects_invalid_barrier_terms(
    field: str, value: object, message: str
) -> None:
    with pytest.raises(InvalidContractError, match=message):
        make_contract(**{field: value})


def test_contract_rejects_non_european_exercise() -> None:
    with pytest.raises(InvalidContractError, match="European"):
        make_contract(exercise_style=ExerciseStyle.AMERICAN)
