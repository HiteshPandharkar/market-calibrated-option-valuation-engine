"""Focused provider capability contracts."""

from abc import ABC, abstractmethod
from datetime import date, datetime
from enum import Enum

from pyoptionpricer.market.data.models import (
    HistoricalBar,
    InstrumentReference,
    OptionChain,
)
from pyoptionpricer.market.exceptions import UnsupportedMarketDataCapabilityError
from pyoptionpricer.market.observation import MarketObservation
from pyoptionpricer.market.quote import OptionQuote


class MarketDataCapability(str, Enum):
    LIVE_QUOTE = "LIVE_QUOTE"
    OPTION_CHAIN = "OPTION_CHAIN"
    HISTORICAL_BARS = "HISTORICAL_BARS"
    OPTION_QUOTE = "OPTION_QUOTE"
    INSTRUMENT_REFERENCE = "INSTRUMENT_REFERENCE"
    MARKET_DEPTH = "MARKET_DEPTH"
    OPEN_INTEREST = "OPEN_INTEREST"
    YIELD_CURVE = "YIELD_CURVE"
    DIVIDEND_DATA = "DIVIDEND_DATA"
    VOLATILITY_INPUT = "VOLATILITY_INPUT"


class CapabilityProvider(ABC):
    @property
    @abstractmethod
    def capabilities(self) -> frozenset[MarketDataCapability]:
        """Return capabilities implemented directly by this provider."""

    def require_capability(self, capability: MarketDataCapability) -> None:
        if capability not in self.capabilities:
            raise UnsupportedMarketDataCapabilityError(
                f"{type(self).__name__} does not support {capability.value}"
            )


class InstrumentReferenceProvider(ABC):
    @abstractmethod
    def get_instrument(self, instrument_id: str) -> InstrumentReference:
        """Resolve one canonical instrument identifier."""

    @abstractmethod
    def search_instruments(self, query: str) -> tuple[InstrumentReference, ...]:
        """Search instruments using canonical display fields."""


class QuoteProvider(ABC):
    @abstractmethod
    def get_underlying_quote(
        self, instrument_id: str, timestamp: datetime
    ) -> MarketObservation[float]:
        """Return a canonical underlying last-price observation."""

    @abstractmethod
    def get_option_quote(self, contract_id: str, timestamp: datetime) -> OptionQuote:
        """Return a canonical option quote."""


class HistoricalBarProvider(ABC):
    @abstractmethod
    def get_history(
        self, instrument_id: str, start: datetime, end: datetime
    ) -> tuple[HistoricalBar, ...]:
        """Return canonical bars over an inclusive interval."""


class OptionChainProvider(ABC):
    @abstractmethod
    def get_option_chain(
        self, underlying_id: str, expiry: date, timestamp: datetime
    ) -> OptionChain:
        """Return a normalized chain containing vendor implied volatilities."""
