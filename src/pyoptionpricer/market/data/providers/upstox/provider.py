"""Upstox implementation of project-owned provider interfaces."""

from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime

from pyoptionpricer.market.data.capabilities import (
    CapabilityProvider,
    HistoricalBarProvider,
    InstrumentReferenceProvider,
    MarketDataCapability,
    OptionChainProvider,
    QuoteProvider,
)
from pyoptionpricer.market.curves import DividendYield, YieldCurve
from pyoptionpricer.market.data.models import (
    HistoricalBar,
    InstrumentReference,
    InstrumentType,
    OptionChain,
)
from pyoptionpricer.market.data.provider import MarketDataProvider
from pyoptionpricer.market.data.providers.upstox.client import HTTPUpstoxClient
from pyoptionpricer.market.data.providers.upstox.config import UpstoxConfiguration
from pyoptionpricer.market.data.providers.upstox.mapper import UpstoxMapper
from pyoptionpricer.market.data.providers.upstox.schemas import UpstoxClient
from pyoptionpricer.market.exceptions import (
    MarketDataUnavailableError,
    UnsupportedMarketDataCapabilityError,
)
from pyoptionpricer.market.observation import MarketObservation
from pyoptionpricer.market.quote import OptionQuote

_UPSTOX_CAPABILITIES = frozenset(
    {
        MarketDataCapability.LIVE_QUOTE,
        MarketDataCapability.OPTION_QUOTE,
        MarketDataCapability.INSTRUMENT_REFERENCE,
        MarketDataCapability.HISTORICAL_BARS,
        MarketDataCapability.OPTION_CHAIN,
    }
)


class UpstoxMarketDataProvider(
    MarketDataProvider,
    CapabilityProvider,
    InstrumentReferenceProvider,
    QuoteProvider,
    HistoricalBarProvider,
    OptionChainProvider,
):
    """Normalize Upstox data without exposing raw payloads to consumers."""

    def __init__(
        self,
        client: UpstoxClient,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._client = client
        self._clock = clock or (lambda: datetime.now(UTC))
        self._mapper = UpstoxMapper(self._clock)
        self._instruments: tuple[InstrumentReference, ...] | None = None

    @classmethod
    def from_env(
        cls,
        environ: Mapping[str, str] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> "UpstoxMarketDataProvider":
        """Construct the live adapter from environment-based session data."""
        configuration = UpstoxConfiguration.from_env(environ)
        return cls(HTTPUpstoxClient(configuration), clock=clock)

    @property
    def capabilities(self) -> frozenset[MarketDataCapability]:
        return _UPSTOX_CAPABILITIES

    def get_instrument(self, instrument_id: str) -> InstrumentReference:
        matches = [
            item
            for item in self._load_instruments()
            if instrument_id in {item.instrument_id, item.vendor_instrument_id}
        ]
        if not matches:
            raise MarketDataUnavailableError(
                f"Upstox has no instrument identifier {instrument_id!r}"
            )
        if len(matches) > 1:
            raise MarketDataUnavailableError(
                f"Upstox instrument identifier {instrument_id!r} is ambiguous"
            )
        return matches[0]

    def search_instruments(self, query: str) -> tuple[InstrumentReference, ...]:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string")
        normalized = query.casefold()
        return tuple(
            item
            for item in self._load_instruments()
            if normalized in item.instrument_id.casefold()
            or normalized in item.symbol.casefold()
            or normalized in item.display_symbol.casefold()
        )

    def get_underlying_quote(
        self, instrument_id: str, timestamp: datetime
    ) -> MarketObservation[float]:
        self._require_aware(timestamp, "timestamp")
        instrument = self._resolve_identifier(instrument_id)
        if instrument.instrument_type not in {
            InstrumentType.EQUITY,
            InstrumentType.INDEX,
        }:
            raise MarketDataUnavailableError(
                f"{instrument_id!r} is not an underlying instrument"
            )
        payload = self._client.fetch_full_quote(instrument.vendor_instrument_id)
        return self._mapper.map_underlying_quote(
            payload, instrument.vendor_instrument_id
        )

    def get_spot(
        self, symbol: str, timestamp: datetime
    ) -> MarketObservation[float]:
        return self.get_underlying_quote(symbol, timestamp)

    def get_option_quote(self, contract_id: str, timestamp: datetime) -> OptionQuote:
        self._require_aware(timestamp, "timestamp")
        instrument = self._resolve_identifier(contract_id)
        if instrument.instrument_type is not InstrumentType.OPTION:
            raise MarketDataUnavailableError(f"{contract_id!r} is not an option")
        payload = self._client.fetch_full_quote(instrument.vendor_instrument_id)
        return self._mapper.map_option_quote(payload, instrument.vendor_instrument_id)

    def get_option_chain(
        self, underlying_id: str, expiry: date, timestamp: datetime
    ) -> OptionChain:
        self._require_aware(timestamp, "timestamp")
        if not isinstance(expiry, date):
            raise TypeError("expiry must be a date")
        underlying = self._resolve_identifier(underlying_id)
        if underlying.instrument_type not in {
            InstrumentType.EQUITY,
            InstrumentType.INDEX,
        }:
            raise MarketDataUnavailableError(
                f"{underlying_id!r} is not an underlying instrument"
            )
        instruments = self._load_instruments()
        vendor_to_canonical = {
            instrument.vendor_instrument_id: instrument.instrument_id
            for instrument in instruments
        }
        payload = self._client.fetch_option_chain(
            underlying.vendor_instrument_id, expiry.isoformat()
        )
        return self._mapper.map_option_chain(
            payload, underlying.instrument_id, vendor_to_canonical
        )

    def get_history(
        self, instrument_id: str, start: datetime, end: datetime
    ) -> tuple[HistoricalBar, ...]:
        self._require_interval(start, end)
        instrument = self._resolve_identifier(instrument_id)
        payload = self._client.fetch_historical_candles(
            instrument.vendor_instrument_id,
            start.date().isoformat(),
            end.date().isoformat(),
        )
        bars = self._mapper.map_historical_bars(payload)
        matching = tuple(bar for bar in bars if start <= bar.timestamp <= end)
        if not matching:
            raise MarketDataUnavailableError(
                f"Upstox has no historical bars for {instrument_id!r} in the interval"
            )
        return matching

    def get_price_history(
        self, symbol: str, start: datetime, end: datetime
    ) -> tuple[MarketObservation[float], ...]:
        return tuple(
            MarketObservation(
                value=bar.close,
                timestamp=bar.timestamp,
                source=bar.source or "UPSTOX",
                field="close_price",
                dataset=bar.dataset,
                retrieved_at=bar.retrieved_at,
            )
            for bar in self.get_history(symbol, start, end)
        )

    def get_yield_curve(
        self, currency: str, timestamp: datetime
    ) -> YieldCurve:
        self._unsupported(MarketDataCapability.YIELD_CURVE)

    def get_dividend_data(
        self, symbol: str, timestamp: datetime
    ) -> DividendYield:
        self._unsupported(MarketDataCapability.DIVIDEND_DATA)

    def get_volatility_input(
        self, symbol: str, timestamp: datetime
    ) -> MarketObservation[float]:
        self._unsupported(MarketDataCapability.VOLATILITY_INPUT)

    def _load_instruments(self) -> tuple[InstrumentReference, ...]:
        if self._instruments is None:
            self._instruments = self._mapper.map_instruments(
                self._client.fetch_instruments()
            )
        return self._instruments

    def _resolve_identifier(self, identifier: str) -> InstrumentReference:
        matches = [
            item
            for item in self._load_instruments()
            if identifier
            in {item.instrument_id, item.symbol, item.vendor_instrument_id}
        ]
        if not matches:
            raise MarketDataUnavailableError(
                "Upstox has no canonical, vendor, or symbol identifier "
                f"{identifier!r}"
            )
        if len(matches) > 1:
            raise MarketDataUnavailableError(
                f"Upstox canonical identifier {identifier!r} is ambiguous"
            )
        return matches[0]

    def _unsupported(self, capability: MarketDataCapability) -> None:
        try:
            self.require_capability(capability)
        except UnsupportedMarketDataCapabilityError:
            raise
        raise AssertionError("unsupported provider method declared as supported")

    @staticmethod
    def _require_aware(value: datetime, field: str) -> None:
        if not isinstance(value, datetime):
            raise TypeError(f"{field} must be a datetime")
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"{field} must be timezone-aware")

    @classmethod
    def _require_interval(cls, start: datetime, end: datetime) -> None:
        cls._require_aware(start, "start")
        cls._require_aware(end, "end")
        if start > end:
            raise ValueError("start must not be after end")
