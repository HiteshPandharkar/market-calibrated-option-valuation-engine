from datetime import date, datetime

import pytest

from pyoptionpricer import (
    AssetClass,
    BermudanExercise,
    Currency,
    ExerciseStyle,
    OptionType,
    VanillaOptionContract,
)
from pyoptionpricer.domain.option_contract import InvalidContractError


def make_contract(**overrides: object) -> VanillaOptionContract:
    values = {
        "underlying": "NIFTY",
        "strike": 25000.0,
        "expiry": date(2026, 12, 31),
        "option_type": OptionType.CALL,
        "exercise_style": ExerciseStyle.EUROPEAN,
        "asset_class": AssetClass.INDEX,
        "exchange": "NSE",
        "contract_symbol": "NIFTY26DEC25000CE",
        "currency": Currency.INR,
    }
    values.update(overrides)
    return VanillaOptionContract(**values)  # type: ignore[arg-type]


def test_option_contract_preserves_static_terms() -> None:
    contract = make_contract()

    assert contract.underlying == "NIFTY"
    assert contract.strike == 25000.0
    assert contract.currency is Currency.INR


@pytest.mark.parametrize("strike", [0.0, -1.0, float("nan"), float("inf"), True])
def test_option_contract_rejects_invalid_strike(strike: object) -> None:
    with pytest.raises(InvalidContractError, match="strike"):
        make_contract(strike=strike)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("underlying", " "),
        ("expiry", datetime(2026, 12, 31)),
        ("option_type", "CALL"),
        ("exercise_style", "EUROPEAN"),
        ("asset_class", "INDEX"),
        ("currency", "INR"),
    ],
)
def test_option_contract_rejects_invalid_domain_terms(field: str, value: object) -> None:
    with pytest.raises(InvalidContractError, match=field):
        make_contract(**{field: value})


def test_bermudan_schedule_is_normalized_deterministically() -> None:
    expiry = date(2026, 12, 31)
    first_exercise = date(2026, 9, 30)

    schedule = BermudanExercise((expiry, first_exercise))
    contract = make_contract(
        exercise_style=ExerciseStyle.BERMUDAN,
        exercise_schedule=schedule,
    )

    assert schedule.exercise_dates == (first_exercise, expiry)
    assert contract.exercise_schedule is schedule


@pytest.mark.parametrize(
    ("dates", "message"),
    [
        ((), "empty"),
        ((date(2026, 12, 31), date(2026, 12, 31)), "duplicates"),
        ((datetime(2026, 12, 31),), "only dates"),
    ],
)
def test_bermudan_schedule_rejects_invalid_dates(
    dates: tuple[date, ...], message: str
) -> None:
    with pytest.raises(InvalidContractError, match=message):
        BermudanExercise(dates)


def test_bermudan_contract_requires_expiry_and_rejects_later_dates() -> None:
    expiry = date(2026, 12, 31)

    with pytest.raises(InvalidContractError, match="include expiry"):
        make_contract(
            exercise_style=ExerciseStyle.BERMUDAN,
            exercise_schedule=BermudanExercise((date(2026, 9, 30),)),
        )
    with pytest.raises(InvalidContractError, match="after expiry"):
        make_contract(
            exercise_style=ExerciseStyle.BERMUDAN,
            exercise_schedule=BermudanExercise(
                (expiry, date(2027, 1, 1))
            ),
        )


def test_exercise_schedule_is_required_only_for_bermudan_contracts() -> None:
    schedule = BermudanExercise((date(2026, 12, 31),))

    with pytest.raises(InvalidContractError, match="require"):
        make_contract(exercise_style=ExerciseStyle.BERMUDAN)
    with pytest.raises(InvalidContractError, match="only valid"):
        make_contract(exercise_schedule=schedule)
