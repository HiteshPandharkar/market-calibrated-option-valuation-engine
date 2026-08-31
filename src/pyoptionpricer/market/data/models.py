"""Canonical, provider-independent market-data models."""

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum

from pyoptionpricer.domain import OptionType

from pyoptionpricer.market._validation import (
    require_aware_datetime,
    require_finite_number,
    require_non_empty_text,
)
from pyoptionpricer.market.exceptions import MarketDataValidationError
from pyoptionpricer.market.observation import MarketObservation
from pyoptionpricer.market.quote import OptionQuote


class InstrumentType(str, Enum):
    EQUITY = "EQUITY"
    INDEX = "INDEX"
    OPTION = "OPTION"
    FUTURE = "FUTURE"


class MarketSegment(str, Enum):
    EQUITY_CASH = "EQUITY_CASH"
    EQUITY_DERIVATIVES = "EQUITY_DERIVATIVES"
    INDEX_DERIVATIVES = "INDEX_DERIVATIVES"
    CURRENCY_DERIVATIVES = "CURRENCY_DERIVATIVES"
    COMMODITY_DERIVATIVES = "COMMODITY_DERIVATIVES"


@dataclass(frozen=True, slots=True)
class InstrumentReference:
    """Canonical identity and contract metadata for a listed instrument."""

    instrument_id: str
    instrument_type: InstrumentType
    symbol: str
    display_symbol: str
    exchange: str
    segment: MarketSegment
    currency: str
    vendor: str
    vendor_instrument_id: str
    underlying_id: str | None = None
    option_type: OptionType | None = None
    strike: float | None = None
    expiry: date | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "instrument_id",
            "symbol",
            "display_symbol",
            "exchange",
            "currency",
            "vendor",
            "vendor_instrument_id",
        ):
            require_non_empty_text(
                getattr(self, field_name), field_name, MarketDataValidationError
            )
        if self.strike is not None:
            require_finite_number(self.strike, "strike", MarketDataValidationError)
            if self.strike <= 0:
                raise MarketDataValidationError("strike must be positive")
        if self.instrument_type is InstrumentType.OPTION:
            if self.option_type is None or self.strike is None or self.expiry is None:
                raise MarketDataValidationError(
                    "option instruments require option_type, strike, and expiry"
                )


@dataclass(frozen=True, slots=True)
class HistoricalBar:
    """Canonical OHLCV observation independent of vendor candle ordering."""

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    open_interest: float | None = None
    source: str | None = None
    dataset: str | None = None
    retrieved_at: datetime | None = None

    def __post_init__(self) -> None:
        require_aware_datetime(self.timestamp, "timestamp", MarketDataValidationError)
        for field_name in ("open", "high", "low", "close", "volume"):
            require_finite_number(
                getattr(self, field_name), field_name, MarketDataValidationError
            )
        if min(self.open, self.high, self.low, self.close) <= 0:
            raise MarketDataValidationError("OHLC prices must be positive")
        if self.low > min(self.open, self.close) or self.high < max(
            self.open, self.close
        ):
            raise MarketDataValidationError("OHLC prices are inconsistent")
        if self.high < self.low:
            raise MarketDataValidationError("high must not be below low")
        if self.volume < 0:
            raise MarketDataValidationError("volume must not be negative")
        if self.open_interest is not None:
            require_finite_number(
                self.open_interest, "open_interest", MarketDataValidationError
            )
            if self.open_interest < 0:
                raise MarketDataValidationError(
                    "open_interest must not be negative"
                )
        if self.source is not None:
            require_non_empty_text(self.source, "source", MarketDataValidationError)
        if self.dataset is not None:
            require_non_empty_text(self.dataset, "dataset", MarketDataValidationError)
        if self.retrieved_at is not None:
            require_aware_datetime(
                self.retrieved_at, "retrieved_at", MarketDataValidationError
            )

    @property
    def source_vendor(self) -> str | None:
        return self.source

    @property
    def source_dataset(self) -> str | None:
        return self.dataset


@dataclass(frozen=True, slots=True)
class OptionChainEntry:
    """One normalized option-chain contract and its observed market data."""

    contract_id: str
    underlying_id: str
    expiry: date
    strike: float
    option_type: OptionType
    quote: OptionQuote
    vendor_implied_volatility: MarketObservation[float] | None

    def __post_init__(self) -> None:
        require_non_empty_text(
            self.contract_id, "contract_id", MarketDataValidationError
        )
        require_non_empty_text(
            self.underlying_id, "underlying_id", MarketDataValidationError
        )
        require_finite_number(self.strike, "strike", MarketDataValidationError)
        if self.strike <= 0:
            raise MarketDataValidationError("strike must be positive")
        if not isinstance(self.expiry, date):
            raise MarketDataValidationError("expiry must be a date")
        if not isinstance(self.option_type, OptionType):
            raise MarketDataValidationError("option_type must be an OptionType")
        if not isinstance(self.quote, OptionQuote):
            raise MarketDataValidationError("quote must be an OptionQuote")
        if self.vendor_implied_volatility is not None:
            observation = self.vendor_implied_volatility
            if not isinstance(observation, MarketObservation):
                raise MarketDataValidationError(
                    "vendor_implied_volatility must be a MarketObservation"
                )
            require_finite_number(
                observation.value,
                "vendor_implied_volatility.value",
                MarketDataValidationError,
            )


@dataclass(frozen=True, slots=True)
class OptionChain:
    """Provider-independent option chain for one underlying and capture."""

    underlying_id: str
    entries: tuple[OptionChainEntry, ...]

    def __post_init__(self) -> None:
        require_non_empty_text(
            self.underlying_id, "underlying_id", MarketDataValidationError
        )
        if not isinstance(self.entries, tuple) or not self.entries:
            raise MarketDataValidationError("option chain must contain entries")
        if any(not isinstance(entry, OptionChainEntry) for entry in self.entries):
            raise MarketDataValidationError(
                "option chain entries must be OptionChainEntry values"
            )
        if any(entry.underlying_id != self.underlying_id for entry in self.entries):
            raise MarketDataValidationError(
                "option chain entries must share the chain underlying_id"
            )
        keys = [
            (entry.expiry, entry.strike, entry.option_type)
            for entry in self.entries
        ]
        if len(keys) != len(set(keys)):
            raise MarketDataValidationError(
                "option chain contains duplicate expiry/strike/option-type entries"
            )
