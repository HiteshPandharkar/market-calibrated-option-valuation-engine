"""Normalized option quote model."""

from dataclasses import dataclass
from datetime import datetime

from pyoptionpricer.market._validation import (
    require_aware_datetime,
    require_finite_number,
    require_non_empty_text,
)
from pyoptionpricer.market.exceptions import InvalidMarketQuoteError


@dataclass(frozen=True, slots=True)
class OptionQuote:
    """A point-in-time option quote in canonical project terminology."""

    bid: float | None
    ask: float | None
    last: float | None
    timestamp: datetime
    source: str | None = None
    dataset: str | None = None
    retrieved_at: datetime | None = None

    def __post_init__(self) -> None:
        require_aware_datetime(self.timestamp, "timestamp", InvalidMarketQuoteError)

        for field_name in ("bid", "ask", "last"):
            value = getattr(self, field_name)
            if value is None:
                continue
            require_finite_number(value, field_name, InvalidMarketQuoteError)
            if value < 0:
                raise InvalidMarketQuoteError(f"{field_name} must not be negative")

        if self.bid is not None and self.ask is not None and self.bid > self.ask:
            raise InvalidMarketQuoteError("crossed market: bid must not exceed ask")

        if self.source is not None:
            require_non_empty_text(self.source, "source", InvalidMarketQuoteError)
        if self.dataset is not None:
            require_non_empty_text(self.dataset, "dataset", InvalidMarketQuoteError)
        if self.retrieved_at is not None:
            require_aware_datetime(
                self.retrieved_at, "retrieved_at", InvalidMarketQuoteError
            )

    def mid(self) -> float | None:
        """Return the bid/ask midpoint, or ``None`` when either side is absent."""
        if self.bid is None or self.ask is None:
            return None
        return (self.bid + self.ask) / 2.0

    @property
    def bid_price(self) -> float | None:
        return self.bid

    @property
    def ask_price(self) -> float | None:
        return self.ask

    @property
    def last_price(self) -> float | None:
        return self.last

    @property
    def source_vendor(self) -> str | None:
        return self.source

    @property
    def source_dataset(self) -> str | None:
        return self.dataset

    @property
    def source_timestamp(self) -> datetime:
        return self.timestamp
