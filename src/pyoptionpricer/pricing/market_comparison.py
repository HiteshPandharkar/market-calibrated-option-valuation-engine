"""Provider-neutral comparison of theoretical and quoted option values."""

from dataclasses import dataclass
from math import isfinite

from pyoptionpricer.market import OptionQuote


class MarketComparisonError(ValueError):
    """Raised when a model value and quote cannot be compared."""


@dataclass(frozen=True, slots=True)
class MarketComparison:
    """Theoretical value compared with a two-sided market quote.

    ``absolute_difference`` is expressed in the quote currency and
    ``percentage_difference`` is the absolute difference as a percentage of
    the market midpoint.
    """

    model_price: float
    market_bid: float
    market_ask: float
    market_mid: float
    absolute_difference: float
    percentage_difference: float


def compare_to_market(model_price: float, quote: OptionQuote) -> MarketComparison:
    """Compare a non-negative model value with a canonical option quote.

    A two-sided quote is required because neither the last trade nor a
    one-sided market is a substitute for the current executable spread. A
    positive midpoint is required to define a percentage difference.
    """

    if isinstance(model_price, bool) or not isinstance(model_price, (int, float)):
        raise MarketComparisonError("model_price must be a number")
    normalized_model_price = float(model_price)
    if not isfinite(normalized_model_price) or normalized_model_price < 0:
        raise MarketComparisonError("model_price must be finite and non-negative")
    if not isinstance(quote, OptionQuote):
        raise TypeError("quote must be an OptionQuote")

    market_bid = quote.bid
    market_ask = quote.ask
    if market_bid is None or market_ask is None:
        raise MarketComparisonError(
            "market comparison requires both bid and ask prices"
        )
    market_mid = (market_bid + market_ask) / 2.0
    if market_mid <= 0:
        raise MarketComparisonError(
            "market midpoint must be positive to calculate percentage difference"
        )

    absolute_difference = abs(normalized_model_price - market_mid)
    return MarketComparison(
        model_price=normalized_model_price,
        market_bid=market_bid,
        market_ask=market_ask,
        market_mid=market_mid,
        absolute_difference=absolute_difference,
        percentage_difference=absolute_difference / market_mid * 100.0,
    )
