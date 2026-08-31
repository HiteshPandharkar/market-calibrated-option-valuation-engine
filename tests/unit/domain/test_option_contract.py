from datetime import date, datetime

import pytest

from pyoptionpricer import (
    AssetClass,
    Currency,
    ExerciseStyle,
    OptionContract,
    OptionType,
)
from pyoptionpricer.domain.option_contract import InvalidContractError


def make_contract(**overrides: object) -> OptionContract:
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
    return OptionContract(**values)  # type: ignore[arg-type]


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
