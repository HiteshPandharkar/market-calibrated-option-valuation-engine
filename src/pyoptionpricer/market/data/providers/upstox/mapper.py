"""Anti-corruption mapping from Upstox payloads to canonical models."""

from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, date, datetime
from math import isfinite
from typing import cast

from pyoptionpricer.market.data.models import (
    HistoricalBar,
    InstrumentReference,
    InstrumentType,
    MarketSegment,
    OptionChain,
    OptionChainEntry,
    OptionType,
)
from pyoptionpricer.market.data.providers.upstox.errors import UpstoxPayloadError
from pyoptionpricer.market.data.providers.upstox.schemas import JsonObject, JsonValue
from pyoptionpricer.market.exceptions import MarketDataValidationError
from pyoptionpricer.market.observation import MarketObservation
from pyoptionpricer.market.quote import OptionQuote

_SEGMENTS = {
    "NSE_EQ": MarketSegment.EQUITY_CASH,
    "BSE_EQ": MarketSegment.EQUITY_CASH,
    "NSE_INDEX": MarketSegment.EQUITY_CASH,
    "BSE_INDEX": MarketSegment.EQUITY_CASH,
    "NSE_FO": MarketSegment.EQUITY_DERIVATIVES,
    "BSE_FO": MarketSegment.EQUITY_DERIVATIVES,
    "NCD_FO": MarketSegment.CURRENCY_DERIVATIVES,
    "BCD_FO": MarketSegment.CURRENCY_DERIVATIVES,
    "MCX_FO": MarketSegment.COMMODITY_DERIVATIVES,
    "NSE_COM": MarketSegment.COMMODITY_DERIVATIVES,
}
_INSTRUMENT_TYPES = {
    "EQ": InstrumentType.EQUITY,
    "EQUITY": InstrumentType.EQUITY,
    "INDEX": InstrumentType.INDEX,
    "CE": InstrumentType.OPTION,
    "PE": InstrumentType.OPTION,
    "FUT": InstrumentType.FUTURE,
    "FUTIDX": InstrumentType.FUTURE,
    "FUTSTK": InstrumentType.FUTURE,
    "FUTCOM": InstrumentType.FUTURE,
    "FUTCUR": InstrumentType.FUTURE,
}
_OPTION_TYPES = {"CE": OptionType.CALL, "PE": OptionType.PUT}


class UpstoxMapper:
    """Map and validate all raw vendor values at the adapter boundary."""

    def __init__(self, clock: Callable[[], datetime]) -> None:
        self._clock = clock

    def map_instruments(
        self, payloads: Sequence[JsonObject]
    ) -> tuple[InstrumentReference, ...]:
        supported_payloads = tuple(
            payload
            for payload in payloads
            if self._is_supported_bulk_instrument(payload)
        )
        vendor_to_canonical: dict[str, str] = {}
        for payload in supported_payloads:
            vendor_id = self._required_text(payload, "instrument_key", "instrument")
            vendor_to_canonical[vendor_id] = self._canonical_instrument_id(payload)

        mapped = tuple(
            self.map_instrument(payload, vendor_to_canonical)
            for payload in supported_payloads
        )
        instrument_ids = [instrument.instrument_id for instrument in mapped]
        if len(instrument_ids) != len(set(instrument_ids)):
            raise UpstoxPayloadError(
                "Upstox instruments map to duplicate canonical instrument IDs"
            )
        return mapped

    @staticmethod
    def _is_supported_bulk_instrument(payload: JsonObject) -> bool:
        """Ignore valid but out-of-scope entries in the complete BOD master."""
        segment = payload.get("segment")
        if (
            isinstance(segment, str)
            and segment.strip()
            and segment.strip().upper() not in _SEGMENTS
        ):
            return False
        instrument_type = payload.get("instrument_type")
        if (
            isinstance(instrument_type, str)
            and instrument_type.strip()
            and instrument_type.strip().upper() not in _INSTRUMENT_TYPES
        ):
            return False
        return True

    def map_instrument(
        self,
        payload: JsonObject,
        vendor_to_canonical: Mapping[str, str] | None = None,
    ) -> InstrumentReference:
        context = "instrument"
        vendor_id = self._required_text(payload, "instrument_key", context)
        vendor_type = self._required_text(payload, "instrument_type", context).upper()
        try:
            instrument_type = _INSTRUMENT_TYPES[vendor_type]
        except KeyError as error:
            raise UpstoxPayloadError(
                f"Upstox instrument has unsupported instrument_type {vendor_type!r}"
            ) from error

        segment = self._canonical_segment(payload)

        symbol = self._required_text(payload, "trading_symbol", context)
        display_symbol = self._first_text(
            payload, ("short_name", "name", "trading_symbol"), context
        )
        exchange = self._required_text(payload, "exchange", context).upper()
        if exchange not in {"NSE", "BSE", "NCD", "BCD", "MCX"}:
            raise UpstoxPayloadError(
                f"Upstox instrument has unsupported exchange {exchange!r}"
            )

        underlying_vendor_id = self._optional_text(payload.get("underlying_key"))
        underlying_id = (
            vendor_to_canonical.get(underlying_vendor_id)
            if vendor_to_canonical is not None and underlying_vendor_id is not None
            else None
        )
        try:
            return InstrumentReference(
                instrument_id=self._canonical_instrument_id(payload),
                instrument_type=instrument_type,
                symbol=symbol,
                display_symbol=display_symbol,
                exchange=exchange,
                segment=segment,
                currency="INR",
                vendor="UPSTOX",
                vendor_instrument_id=vendor_id,
                underlying_id=underlying_id,
                option_type=_OPTION_TYPES.get(vendor_type),
                strike=(
                    self._required_number(payload, "strike_price", context)
                    if instrument_type is InstrumentType.OPTION
                    else None
                ),
                expiry=(
                    self._expiry(payload.get("expiry"), context)
                    if instrument_type is InstrumentType.OPTION
                    else None
                ),
            )
        except MarketDataValidationError as error:
            raise UpstoxPayloadError(f"Invalid Upstox {context}: {error}") from error

    def map_underlying_quote(
        self, payload: JsonObject, vendor_instrument_id: str
    ) -> MarketObservation[float]:
        quote = self._quote_entry(payload, vendor_instrument_id)
        value = self._required_number(quote, "last_price", "market quote")
        if value <= 0:
            raise UpstoxPayloadError("Upstox market quote last_price must be positive")
        timestamp = self._quote_timestamp(quote)
        try:
            return MarketObservation(
                value=value,
                timestamp=timestamp,
                source="UPSTOX",
                field="last_price",
                dataset="MARKET_QUOTE",
                retrieved_at=self._aware_now(),
            )
        except MarketDataValidationError as error:
            raise UpstoxPayloadError(f"Invalid Upstox market quote: {error}") from error

    def map_option_quote(
        self, payload: JsonObject, vendor_instrument_id: str
    ) -> OptionQuote:
        quote = self._quote_entry(payload, vendor_instrument_id)
        depth = quote.get("depth")
        depth_mapping = depth if isinstance(depth, Mapping) else {}
        try:
            return OptionQuote(
                bid=self._depth_price(depth_mapping.get("buy"), "buy"),
                ask=self._depth_price(depth_mapping.get("sell"), "sell"),
                last=self._required_number(quote, "last_price", "option quote"),
                timestamp=self._quote_timestamp(quote),
                source="UPSTOX",
                dataset="MARKET_QUOTE",
                retrieved_at=self._aware_now(),
            )
        except MarketDataValidationError as error:
            raise UpstoxPayloadError(f"Invalid Upstox option quote: {error}") from error

    def map_historical_bars(self, payload: JsonObject) -> tuple[HistoricalBar, ...]:
        data = payload.get("data")
        if not isinstance(data, Mapping):
            raise UpstoxPayloadError("Upstox historical response requires data object")
        candles = data.get("candles")
        if not isinstance(candles, Sequence) or isinstance(candles, (str, bytes)):
            raise UpstoxPayloadError(
                "Upstox historical response requires candles array"
            )

        retrieved_at = self._aware_now()
        bars = []
        for index, candle in enumerate(candles):
            context = f"historical candle {index}"
            if not isinstance(candle, Sequence) or isinstance(candle, (str, bytes)):
                raise UpstoxPayloadError(f"Upstox {context} must be an array")
            if len(candle) < 6:
                raise UpstoxPayloadError(
                    f"Upstox {context} requires timestamp, OHLC, and volume"
                )
            try:
                bars.append(
                    HistoricalBar(
                        timestamp=self._timestamp(candle[0], context),
                        open=self._number(candle[1], "open", context),
                        high=self._number(candle[2], "high", context),
                        low=self._number(candle[3], "low", context),
                        close=self._number(candle[4], "close", context),
                        volume=self._number(candle[5], "volume", context),
                        open_interest=(
                            self._number(candle[6], "open_interest", context)
                            if len(candle) > 6 and candle[6] is not None
                            else None
                        ),
                        source="UPSTOX",
                        dataset="HISTORICAL_CANDLE",
                        retrieved_at=retrieved_at,
                    )
                )
            except MarketDataValidationError as error:
                raise UpstoxPayloadError(
                    f"Invalid Upstox {context}: {error}"
                ) from error
        bars.sort(key=lambda bar: bar.timestamp)
        timestamps = [bar.timestamp for bar in bars]
        if len(timestamps) != len(set(timestamps)):
            raise UpstoxPayloadError("Upstox historical response has duplicate candles")
        return tuple(bars)

    def map_option_chain(
        self,
        payload: JsonObject,
        underlying_id: str,
        vendor_to_canonical: Mapping[str, str],
    ) -> OptionChain:
        """Normalize Upstox option-chain rows and decimalize vendor IVs."""
        data = payload.get("data")
        if not isinstance(data, Sequence) or isinstance(data, (str, bytes)):
            raise UpstoxPayloadError("Upstox option chain requires data array")
        captured_at = self._aware_now()
        entries: list[OptionChainEntry] = []
        for row_index, row in enumerate(data):
            if not isinstance(row, Mapping):
                raise UpstoxPayloadError(
                    f"Upstox option chain row {row_index} must be an object"
                )
            context = f"option chain row {row_index}"
            expiry = self._expiry(row.get("expiry"), context)
            strike = self._required_number(row, "strike_price", context)
            for vendor_field, option_type in (
                ("call_options", OptionType.CALL),
                ("put_options", OptionType.PUT),
            ):
                option = row.get(vendor_field)
                if option is None:
                    continue
                if not isinstance(option, Mapping):
                    raise UpstoxPayloadError(
                        f"Upstox {context} {vendor_field} must be an object"
                    )
                vendor_contract_id = self._required_text(
                    option, "instrument_key", f"{context} {vendor_field}"
                )
                contract_id = vendor_to_canonical.get(vendor_contract_id)
                if contract_id is None:
                    raise UpstoxPayloadError(
                        "Upstox option chain references an instrument absent from "
                        "the normalized instrument master"
                    )
                market_data = option.get("market_data")
                if not isinstance(market_data, Mapping):
                    raise UpstoxPayloadError(
                        f"Upstox {context} {vendor_field} requires market_data"
                    )
                greeks = option.get("option_greeks")
                greek_data = greeks if isinstance(greeks, Mapping) else {}
                raw_iv = greek_data.get("iv", market_data.get("iv"))
                implied_volatility = (
                    None
                    if raw_iv is None
                    else MarketObservation(
                        value=self._decimal_implied_volatility(raw_iv, context),
                        timestamp=captured_at,
                        source="UPSTOX",
                        field="vendor_implied_volatility",
                        dataset="OPTION_CHAIN",
                        retrieved_at=captured_at,
                    )
                )
                try:
                    entries.append(
                        OptionChainEntry(
                            contract_id=contract_id,
                            underlying_id=underlying_id,
                            expiry=expiry,
                            strike=strike,
                            option_type=option_type,
                            quote=OptionQuote(
                                bid=self._optional_number(
                                    market_data.get("bid_price"),
                                    "bid_price",
                                    context,
                                ),
                                ask=self._optional_number(
                                    market_data.get("ask_price"),
                                    "ask_price",
                                    context,
                                ),
                                last=self._optional_number(
                                    market_data.get("ltp"), "ltp", context
                                ),
                                timestamp=captured_at,
                                source="UPSTOX",
                                dataset="OPTION_CHAIN",
                                retrieved_at=captured_at,
                            ),
                            vendor_implied_volatility=implied_volatility,
                        )
                    )
                except MarketDataValidationError as error:
                    raise UpstoxPayloadError(
                        f"Invalid Upstox {context}: {error}"
                    ) from error
        try:
            return OptionChain(underlying_id, tuple(entries))
        except MarketDataValidationError as error:
            raise UpstoxPayloadError(f"Invalid Upstox option chain: {error}") from error

    def _decimal_implied_volatility(self, value: JsonValue, context: str) -> float:
        """Normalize REST-chain percentage IVs while accepting decimal payloads."""
        number = self._number(value, "iv", context)
        return number / 100.0 if abs(number) > 3.0 else number

    def _optional_number(
        self, value: JsonValue, field: str, context: str
    ) -> float | None:
        return None if value is None else self._number(value, field, context)

    def _quote_entry(
        self, payload: JsonObject, vendor_instrument_id: str
    ) -> Mapping[str, JsonValue]:
        data = payload.get("data")
        if not isinstance(data, Mapping) or not data:
            raise UpstoxPayloadError("Upstox market quote response has no data")
        entry = data.get(vendor_instrument_id)
        if entry is None:
            entry = data.get(vendor_instrument_id.replace("|", ":"))
        if entry is None and len(data) == 1:
            entry = next(iter(data.values()))
        if not isinstance(entry, Mapping):
            raise UpstoxPayloadError(
                "Upstox market quote response has no matching instrument"
            )
        return cast(Mapping[str, JsonValue], entry)

    def _quote_timestamp(self, quote: Mapping[str, JsonValue]) -> datetime:
        value = quote.get("timestamp", quote.get("last_trade_time"))
        return self._timestamp(value, "market quote")

    def _depth_price(self, value: JsonValue, side: str) -> float | None:
        if value is None:
            return None
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
            raise UpstoxPayloadError(
                f"Upstox option quote {side} depth must be an array"
            )
        if not value:
            return None
        level = value[0]
        if not isinstance(level, Mapping):
            raise UpstoxPayloadError(
                f"Upstox option quote {side} depth level must be an object"
            )
        price = level.get("price")
        return (
            None
            if price is None
            else self._number(price, f"{side} price", "option quote")
        )

    def _canonical_instrument_id(self, payload: JsonObject) -> str:
        segment = self._canonical_segment(payload)
        exchange = self._required_text(payload, "exchange", "instrument").upper()
        symbol = self._required_text(payload, "trading_symbol", "instrument")
        return f"{segment.value}:{exchange}:{symbol}"

    def _canonical_segment(self, payload: JsonObject) -> MarketSegment:
        vendor_segment = self._required_text(
            payload, "segment", "instrument"
        ).upper()
        try:
            segment = _SEGMENTS[vendor_segment]
        except KeyError as error:
            raise UpstoxPayloadError(
                f"Upstox instrument has unsupported segment {vendor_segment!r}"
            ) from error
        if (
            segment is MarketSegment.EQUITY_DERIVATIVES
            and str(payload.get("underlying_type", "")).upper() == "INDEX"
        ):
            return MarketSegment.INDEX_DERIVATIVES
        return segment

    def _expiry(self, value: JsonValue, context: str) -> date:
        if isinstance(value, bool) or value is None:
            raise UpstoxPayloadError(f"Upstox {context} requires expiry")
        if isinstance(value, (int, float)):
            seconds = (
                float(value) / 1000
                if float(value) > 10_000_000_000
                else float(value)
            )
            try:
                return datetime.fromtimestamp(seconds, tz=UTC).date()
            except (OSError, OverflowError, ValueError) as error:
                raise UpstoxPayloadError(
                    f"Upstox {context} expiry is invalid"
                ) from error
        if isinstance(value, str):
            try:
                return date.fromisoformat(value.strip())
            except ValueError as error:
                raise UpstoxPayloadError(
                    f"Upstox {context} expiry must be ISO date or epoch"
                ) from error
        raise UpstoxPayloadError(f"Upstox {context} expiry has invalid type")

    def _timestamp(self, value: JsonValue, context: str) -> datetime:
        if isinstance(value, bool) or value is None:
            raise UpstoxPayloadError(f"Upstox {context} requires timestamp")
        if isinstance(value, (int, float)):
            seconds = (
                float(value) / 1000
                if float(value) > 10_000_000_000
                else float(value)
            )
            try:
                return datetime.fromtimestamp(seconds, tz=UTC)
            except (OSError, OverflowError, ValueError) as error:
                raise UpstoxPayloadError(
                    f"Upstox {context} timestamp is invalid"
                ) from error
        if isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(
                    value.strip().replace("Z", "+00:00")
                )
            except ValueError as error:
                raise UpstoxPayloadError(
                    f"Upstox {context} timestamp must be ISO-8601"
                ) from error
            if parsed.tzinfo is None or parsed.utcoffset() is None:
                raise UpstoxPayloadError(
                    f"Upstox {context} timestamp must be timezone-aware"
                )
            return parsed
        raise UpstoxPayloadError(f"Upstox {context} timestamp has invalid type")

    def _required_number(
        self, payload: Mapping[str, JsonValue], field: str, context: str
    ) -> float:
        if field not in payload:
            raise UpstoxPayloadError(f"Upstox {context} requires {field}")
        return self._number(payload[field], field, context)

    @staticmethod
    def _number(value: JsonValue, field: str, context: str) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise UpstoxPayloadError(f"Upstox {context} {field} must be numeric")
        number = float(value)
        if not isfinite(number):
            raise UpstoxPayloadError(f"Upstox {context} {field} must be finite")
        return number

    @staticmethod
    def _required_text(payload: JsonObject, field: str, context: str) -> str:
        value = UpstoxMapper._optional_text(payload.get(field))
        if value is None:
            raise UpstoxPayloadError(f"Upstox {context} requires {field}")
        return value

    @staticmethod
    def _first_text(
        payload: JsonObject, fields: Sequence[str], context: str
    ) -> str:
        for field in fields:
            value = UpstoxMapper._optional_text(payload.get(field))
            if value is not None:
                return value
        raise UpstoxPayloadError(
            f"Upstox {context} requires one of {', '.join(fields)}"
        )

    @staticmethod
    def _optional_text(value: JsonValue) -> str | None:
        return value.strip() if isinstance(value, str) and value.strip() else None

    def _aware_now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise UpstoxPayloadError("Upstox adapter clock must be timezone-aware")
        return value
