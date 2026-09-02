from datetime import date

import pytest

from pyoptionpricer import (
    AssetClass,
    AsianOptionContract,
    AveragingMethod,
    ExerciseStyle,
    InvalidContractError,
    LookbackOptionContract,
    OptionProduct,
    OptionType,
    PathMonitoringConvention,
    VanillaPayoff,
)


def terms() -> dict[str, object]:
    return {
        "underlying": "ACME",
        "strike": 100.0,
        "expiry": date(2027, 9, 2),
        "option_type": OptionType.CALL,
        "exercise_style": ExerciseStyle.EUROPEAN,
        "asset_class": AssetClass.EQUITY,
    }


def test_asian_contract_normalizes_explicit_observation_schedule() -> None:
    contract = AsianOptionContract(
        **terms(),
        observation_schedule=(date(2027, 9, 2), date(2027, 3, 3)),
    )

    assert contract.product is OptionProduct.ASIAN
    assert contract.observation_schedule == (date(2027, 3, 3), date(2027, 9, 2))
    assert contract.averaging_method is AveragingMethod.ARITHMETIC
    assert contract.monitoring_convention is PathMonitoringConvention.DISCRETE_DATES
    assert contract.payoff == VanillaPayoff(OptionType.CALL, 100.0)


def test_lookback_contract_normalizes_explicit_monitoring_schedule() -> None:
    contract = LookbackOptionContract(
        **terms(), monitoring_schedule=(date(2027, 9, 2), date(2027, 3, 3))
    )

    assert contract.product is OptionProduct.LOOKBACK
    assert contract.monitoring_schedule == (date(2027, 3, 3), date(2027, 9, 2))
    assert contract.monitoring_convention is PathMonitoringConvention.DISCRETE_DATES


@pytest.mark.parametrize("contract_type,schedule_name", [
    (AsianOptionContract, "observation_schedule"),
    (LookbackOptionContract, "monitoring_schedule"),
])
@pytest.mark.parametrize("schedule", [
    (),
    (date(2027, 3, 3), date(2027, 3, 3)),
    (date(2027, 9, 3),),
    ("2027-03-03",),
])
def test_path_dependent_contracts_reject_malformed_schedules(
    contract_type: type[AsianOptionContract] | type[LookbackOptionContract],
    schedule_name: str,
    schedule: tuple[object, ...],
) -> None:
    with pytest.raises(InvalidContractError, match=schedule_name):
        contract_type(**terms(), **{schedule_name: schedule})


@pytest.mark.parametrize("contract_type,schedule_name", [
    (AsianOptionContract, "observation_schedule"),
    (LookbackOptionContract, "monitoring_schedule"),
])
def test_path_dependent_contracts_reject_non_european_exercise(
    contract_type: type[AsianOptionContract] | type[LookbackOptionContract],
    schedule_name: str,
) -> None:
    values = terms()
    values["exercise_style"] = ExerciseStyle.AMERICAN
    with pytest.raises(InvalidContractError, match="European"):
        contract_type(**values, **{schedule_name: (date(2027, 9, 2),)})
