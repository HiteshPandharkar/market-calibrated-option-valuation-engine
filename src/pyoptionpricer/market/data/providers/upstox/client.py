"""HTTP communication with Upstox; contains no canonical mapping logic."""

from collections.abc import Callable, Mapping, Sequence
import gzip
import json
from typing import Any, cast
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from pyoptionpricer.market.data.providers.upstox.config import UpstoxConfiguration
from pyoptionpricer.market.data.providers.upstox.errors import (
    UpstoxAPIError,
    UpstoxAuthenticationError,
    UpstoxPayloadError,
)
from pyoptionpricer.market.data.providers.upstox.schemas import JsonObject, JsonValue


_USER_AGENT = "PyOptionPricer/0.1 market-data-client"


class HTTPUpstoxClient:
    """Minimal standard-library client for the Upstox endpoints used in V1."""

    def __init__(
        self,
        configuration: UpstoxConfiguration,
        opener: Callable[..., Any] = urlopen,
    ) -> None:
        self._configuration = configuration
        self._opener = opener

    def fetch_instruments(self) -> Sequence[JsonObject]:
        payload = self._request_json(
            self._configuration.instruments_url, authenticated=False
        )
        if not isinstance(payload, list) or not all(
            isinstance(item, Mapping) for item in payload
        ):
            raise UpstoxPayloadError("Upstox instrument file must contain a JSON list")
        return cast(list[JsonObject], payload)

    def fetch_full_quote(self, vendor_instrument_id: str) -> JsonObject:
        payload = self._api_get(
            "/v2/market-quote/quotes",
            {"instrument_key": vendor_instrument_id},
        )
        return self._require_object(payload, "full market quote")

    def fetch_historical_candles(
        self,
        vendor_instrument_id: str,
        from_date: str,
        to_date: str,
    ) -> JsonObject:
        encoded_id = quote(vendor_instrument_id, safe="")
        payload = self._api_get(
            f"/v3/historical-candle/{encoded_id}/days/1/{to_date}/{from_date}",
            {},
        )
        return self._require_object(payload, "historical candles")

    def fetch_option_chain(
        self, vendor_underlying_id: str, expiry_date: str
    ) -> JsonObject:
        payload = self._api_get(
            "/v2/option/chain",
            {
                "instrument_key": vendor_underlying_id,
                "expiry_date": expiry_date,
            },
        )
        return self._require_object(payload, "option chain")

    def _api_get(self, path: str, parameters: Mapping[str, str]) -> JsonValue:
        query = f"?{urlencode(parameters)}" if parameters else ""
        base_url = self._configuration.api_base_url.rstrip("/")
        return self._request_json(f"{base_url}{path}{query}", authenticated=True)

    def _request_json(self, url: str, authenticated: bool) -> JsonValue:
        headers = {
            "Accept": "application/json",
            "Api-Version": "2.0",
            "User-Agent": _USER_AGENT,
        }
        if authenticated:
            headers["Authorization"] = (
                f"Bearer {self._configuration.access_token.strip()}"
            )
        request = Request(url, headers=headers, method="GET")
        try:
            with self._opener(
                request, timeout=self._configuration.timeout_seconds
            ) as response:
                content = response.read()
        except HTTPError as error:
            if error.code in (401, 403):
                raise UpstoxAuthenticationError(
                    "Upstox authentication failed; refresh UPSTOX_ACCESS_TOKEN"
                ) from error
            raise UpstoxAPIError(
                f"Upstox request failed with HTTP status {error.code}"
            ) from error
        except (TimeoutError, URLError) as error:
            raise UpstoxAPIError("Upstox request could not be completed") from error

        if content.startswith(b"\x1f\x8b"):
            try:
                content = gzip.decompress(content)
            except OSError as error:
                raise UpstoxPayloadError(
                    "Upstox response contains invalid gzip data"
                ) from error
        try:
            return cast(JsonValue, json.loads(content.decode("utf-8")))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise UpstoxPayloadError("Upstox returned invalid JSON") from error

    @staticmethod
    def _require_object(payload: JsonValue, dataset: str) -> JsonObject:
        if not isinstance(payload, Mapping):
            raise UpstoxPayloadError(f"Upstox {dataset} response must be an object")
        status = payload.get("status")
        if status != "success":
            raise UpstoxAPIError(f"Upstox {dataset} request was not successful")
        return cast(JsonObject, payload)
