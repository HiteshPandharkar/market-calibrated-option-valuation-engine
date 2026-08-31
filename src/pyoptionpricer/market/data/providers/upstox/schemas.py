"""Private structural types for raw Upstox payloads."""

from collections.abc import Mapping, Sequence
from typing import Protocol, TypeAlias

JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | Mapping[str, "JsonValue"] | Sequence["JsonValue"]
JsonObject: TypeAlias = Mapping[str, JsonValue]


class UpstoxClient(Protocol):
    """Raw transport contract consumed only by the Upstox adapter."""

    def fetch_instruments(self) -> Sequence[JsonObject]: ...

    def fetch_full_quote(self, vendor_instrument_id: str) -> JsonObject: ...

    def fetch_historical_candles(
        self,
        vendor_instrument_id: str,
        from_date: str,
        to_date: str,
    ) -> JsonObject: ...

    def fetch_option_chain(
        self, vendor_underlying_id: str, expiry_date: str
    ) -> JsonObject: ...
