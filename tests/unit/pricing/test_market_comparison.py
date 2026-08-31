from datetime import UTC, datetime

import pytest

from pyoptionpricer import MarketComparison, MarketComparisonError, compare_to_market
from pyoptionpricer.market import OptionQuote


TIMESTAMP = datetime(2026, 8, 30, 11, 59, tzinfo=UTC)


def test_market_comparison_contains_independent_model_and_market_values() -> None:
    quote = OptionQuote(9.0, 11.0, 10.5, TIMESTAMP)

    comparison = compare_to_market(12.5, quote)

    assert isinstance(comparison, MarketComparison)
    assert comparison.model_price == pytest.approx(12.5)
    assert comparison.market_bid == pytest.approx(9.0)
    assert comparison.market_ask == pytest.approx(11.0)
    assert comparison.market_mid == pytest.approx(10.0)
    assert comparison.absolute_difference == pytest.approx(2.5)
    assert comparison.percentage_difference == pytest.approx(25.0)


def test_absolute_difference_is_non_negative_when_model_is_below_market() -> None:
    comparison = compare_to_market(
        7.5, OptionQuote(9.0, 11.0, 10.0, TIMESTAMP)
    )

    assert comparison.absolute_difference == pytest.approx(2.5)
    assert comparison.percentage_difference == pytest.approx(25.0)


@pytest.mark.parametrize(
    "quote",
    [
        OptionQuote(None, 11.0, 10.0, TIMESTAMP),
        OptionQuote(9.0, None, 10.0, TIMESTAMP),
    ],
)
def test_comparison_rejects_quote_without_two_sided_midpoint(
    quote: OptionQuote,
) -> None:
    with pytest.raises(MarketComparisonError, match="both bid and ask"):
        compare_to_market(10.0, quote)


def test_comparison_rejects_zero_midpoint_with_undefined_percentage() -> None:
    quote = OptionQuote(0.0, 0.0, 0.0, TIMESTAMP)

    with pytest.raises(MarketComparisonError, match="midpoint must be positive"):
        compare_to_market(0.0, quote)


@pytest.mark.parametrize("model_price", [-0.01, float("nan"), float("inf"), True])
def test_comparison_rejects_invalid_model_price(model_price: object) -> None:
    quote = OptionQuote(9.0, 11.0, 10.0, TIMESTAMP)

    with pytest.raises(MarketComparisonError, match="model_price"):
        compare_to_market(model_price, quote)  # type: ignore[arg-type]
