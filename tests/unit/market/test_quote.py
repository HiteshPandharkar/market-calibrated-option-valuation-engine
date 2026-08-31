from datetime import UTC, datetime

import pytest

from pyoptionpricer.market import InvalidMarketQuoteError, OptionQuote


TIMESTAMP = datetime(2026, 8, 28, 15, 29, tzinfo=UTC)


def test_midpoint_uses_valid_bid_and_ask() -> None:
    quote = OptionQuote(bid=10.0, ask=12.0, last=11.5, timestamp=TIMESTAMP)

    assert quote.mid() == pytest.approx(11.0)
    assert quote.timestamp is TIMESTAMP


@pytest.mark.parametrize(
    ("bid", "ask"),
    [(None, 12.0), (10.0, None), (None, None)],
)
def test_midpoint_is_explicitly_missing_without_two_sided_quote(
    bid: float | None, ask: float | None
) -> None:
    quote = OptionQuote(bid=bid, ask=ask, last=11.0, timestamp=TIMESTAMP)

    assert quote.mid() is None


def test_crossed_market_is_rejected() -> None:
    with pytest.raises(InvalidMarketQuoteError, match="crossed market"):
        OptionQuote(bid=12.0, ask=10.0, last=11.0, timestamp=TIMESTAMP)


@pytest.mark.parametrize("field_name", ["bid", "ask", "last"])
def test_negative_price_is_rejected(field_name: str) -> None:
    values = {"bid": 10.0, "ask": 12.0, "last": 11.0}
    values[field_name] = -0.01

    with pytest.raises(InvalidMarketQuoteError, match=f"{field_name} must not"):
        OptionQuote(timestamp=TIMESTAMP, **values)


@pytest.mark.parametrize("invalid_value", [float("nan"), float("inf"), True])
def test_non_finite_or_non_price_value_is_rejected(invalid_value: object) -> None:
    with pytest.raises(InvalidMarketQuoteError):
        OptionQuote(bid=invalid_value, ask=12.0, last=11.0, timestamp=TIMESTAMP)  # type: ignore[arg-type]


def test_canonical_price_names_are_accessible() -> None:
    quote = OptionQuote(bid=10.0, ask=12.0, last=11.5, timestamp=TIMESTAMP)

    assert quote.bid_price == 10.0
    assert quote.ask_price == 12.0
    assert quote.last_price == 11.5
