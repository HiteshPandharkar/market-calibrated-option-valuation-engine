from datetime import date
from math import nextafter

import pytest

from pyoptionpricer import (
    AssetClass,
    CashOrNothingPayoff,
    DigitalOptionContract,
    ExerciseStyle,
    InvalidContractError,
    InvalidPayoffError,
    OptionProduct,
    OptionContract,
    OptionType,
    VanillaOptionContract,
)


@pytest.mark.parametrize("option_type", [OptionType.CALL, OptionType.PUT])
def test_cash_or_nothing_payoff_is_zero_at_strike(option_type: OptionType) -> None:
    payoff = CashOrNothingPayoff(option_type, strike=100.0, payout=25.0)

    assert payoff.value_at(100.0) == 0.0
    expected_below = 0.0 if option_type is OptionType.CALL else 25.0
    expected_above = 25.0 if option_type is OptionType.CALL else 0.0
    assert payoff.value_at(nextafter(100.0, 0.0)) == expected_below
    assert payoff.value_at(nextafter(100.0, float("inf"))) == expected_above


@pytest.mark.parametrize("payout", [0.0, -1.0, float("nan"), float("inf"), True])
def test_cash_or_nothing_payoff_rejects_invalid_payout(payout: object) -> None:
    with pytest.raises(InvalidPayoffError, match="payout"):
        CashOrNothingPayoff(OptionType.CALL, 100.0, payout)  # type: ignore[arg-type]


def test_digital_contract_exposes_configurable_payoff() -> None:
    contract = DigitalOptionContract(
        underlying="ACME",
        strike=100.0,
        expiry=date(2027, 9, 1),
        option_type=OptionType.PUT,
        exercise_style=ExerciseStyle.EUROPEAN,
        asset_class=AssetClass.EQUITY,
        cash_payout=12.5,
    )

    assert contract.product is OptionProduct.DIGITAL
    assert contract.payoff == CashOrNothingPayoff(OptionType.PUT, 100.0, 12.5)
    assert isinstance(contract, OptionContract)
    assert not isinstance(contract, VanillaOptionContract)


def test_digital_contract_requires_positive_cash_payout() -> None:
    with pytest.raises(InvalidContractError, match="cash_payout"):
        DigitalOptionContract(
            underlying="ACME",
            strike=100.0,
            expiry=date(2027, 9, 1),
            option_type=OptionType.CALL,
            exercise_style=ExerciseStyle.EUROPEAN,
            asset_class=AssetClass.EQUITY,
            cash_payout=0.0,
        )
