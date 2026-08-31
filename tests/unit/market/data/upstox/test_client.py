from io import BytesIO
import gzip
from urllib.error import HTTPError
from urllib.request import Request

import pytest

from pyoptionpricer.market.data.providers.upstox import (
    HTTPUpstoxClient,
    UpstoxAPIError,
    UpstoxAuthenticationError,
    UpstoxConfiguration,
    UpstoxPayloadError,
)


class FakeResponse:
    def __init__(self, content: bytes) -> None:
        self._content = content

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._content


def test_instrument_master_is_fetched_without_authentication_and_decompressed() -> None:
    requests: list[tuple[Request, float]] = []
    content = gzip.compress(
        b'[{"instrument_key":"NSE_EQ|INE002A01018","trading_symbol":"RELIANCE"}]'
    )

    def opener(request: Request, timeout: float) -> FakeResponse:
        requests.append((request, timeout))
        return FakeResponse(content)

    configuration = UpstoxConfiguration(
        "secret-token",
        instruments_url="https://data.example.test/instruments.json.gz",
        timeout_seconds=2.5,
    )
    client = HTTPUpstoxClient(configuration, opener=opener)

    instruments = client.fetch_instruments()

    request, timeout = requests[0]
    assert request.full_url == configuration.instruments_url
    assert request.method == "GET"
    assert request.get_header("Authorization") is None
    assert request.get_header("Accept") == "application/json"
    assert request.get_header("User-agent") == "PyOptionPricer/0.1 market-data-client"
    assert timeout == pytest.approx(2.5)
    assert instruments[0]["instrument_key"] == "NSE_EQ|INE002A01018"


def test_client_adds_bearer_session_without_exposing_it() -> None:
    requests: list[Request] = []

    def opener(request: Request, timeout: float) -> FakeResponse:
        requests.append(request)
        return FakeResponse(b'{"status":"success","data":{}}')

    client = HTTPUpstoxClient(UpstoxConfiguration("secret-token"), opener=opener)

    client.fetch_full_quote("NSE_EQ|INE002A01018")

    assert requests[0].get_header("Authorization") == "Bearer secret-token"
    assert requests[0].get_header("User-agent") == (
        "PyOptionPricer/0.1 market-data-client"
    )
    assert "secret-token" not in requests[0].full_url
    assert "instrument_key=NSE_EQ%7CINE002A01018" in requests[0].full_url


def test_historical_candles_use_encoded_instrument_and_requested_date_range() -> None:
    requests: list[Request] = []

    def opener(request: Request, timeout: float) -> FakeResponse:
        requests.append(request)
        return FakeResponse(b'{"status":"success","data":{"candles":[]}}')

    client = HTTPUpstoxClient(UpstoxConfiguration("secret-token"), opener=opener)

    payload = client.fetch_historical_candles(
        "NSE_EQ|INE002A01018", "2026-08-01", "2026-08-28"
    )

    request = requests[0]
    assert request.full_url == (
        "https://api.upstox.com/v3/historical-candle/"
        "NSE_EQ%7CINE002A01018/days/1/2026-08-28/2026-08-01"
    )
    assert request.get_header("Authorization") == "Bearer secret-token"
    assert payload["data"] == {"candles": []}


def test_option_chain_uses_underlying_and_expiry_query_parameters() -> None:
    requests: list[Request] = []

    def opener(request: Request, timeout: float) -> FakeResponse:
        requests.append(request)
        return FakeResponse(b'{"status":"success","data":[]}')

    client = HTTPUpstoxClient(UpstoxConfiguration("secret-token"), opener=opener)

    payload = client.fetch_option_chain(
        "NSE_EQ|INE002A01018", "2026-09-29"
    )

    assert requests[0].full_url == (
        "https://api.upstox.com/v2/option/chain?"
        "instrument_key=NSE_EQ%7CINE002A01018&expiry_date=2026-09-29"
    )
    assert payload["data"] == []


@pytest.mark.parametrize("content", [b"{}", b'{"instrument_key":"one"}'])
def test_instrument_master_rejects_non_list_payloads(content: bytes) -> None:
    def opener(request: Request, timeout: float) -> FakeResponse:
        return FakeResponse(content)

    client = HTTPUpstoxClient(UpstoxConfiguration("secret-token"), opener=opener)

    with pytest.raises(UpstoxPayloadError, match="must contain a JSON list"):
        client.fetch_instruments()


def test_authentication_status_is_translated_without_secret() -> None:
    def opener(request: Request, timeout: float) -> FakeResponse:
        raise HTTPError(request.full_url, 401, "Unauthorized", {}, BytesIO())

    client = HTTPUpstoxClient(UpstoxConfiguration("secret-token"), opener=opener)

    with pytest.raises(UpstoxAuthenticationError) as captured:
        client.fetch_full_quote("NSE_EQ|INE002A01018")

    assert "secret-token" not in str(captured.value)


def test_non_authentication_http_failure_is_translated() -> None:
    def opener(request: Request, timeout: float) -> FakeResponse:
        raise HTTPError(request.full_url, 429, "Rate limited", {}, BytesIO())

    client = HTTPUpstoxClient(UpstoxConfiguration("secret-token"), opener=opener)

    with pytest.raises(UpstoxAPIError, match="HTTP status 429"):
        client.fetch_full_quote("NSE_EQ|INE002A01018")


def test_invalid_json_is_translated_to_payload_error() -> None:
    def opener(request: Request, timeout: float) -> FakeResponse:
        return FakeResponse(b"not-json")

    client = HTTPUpstoxClient(UpstoxConfiguration("secret-token"), opener=opener)

    with pytest.raises(UpstoxPayloadError, match="invalid JSON"):
        client.fetch_full_quote("NSE_EQ|INE002A01018")


def test_unsuccessful_api_status_is_translated() -> None:
    def opener(request: Request, timeout: float) -> FakeResponse:
        return FakeResponse(b'{"status":"error","errors":[]}')

    client = HTTPUpstoxClient(UpstoxConfiguration("secret-token"), opener=opener)

    with pytest.raises(UpstoxAPIError, match="not successful"):
        client.fetch_full_quote("NSE_EQ|INE002A01018")
