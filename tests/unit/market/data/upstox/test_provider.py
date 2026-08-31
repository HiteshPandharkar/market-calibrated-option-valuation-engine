from datetime import UTC, date, datetime
import json
from pathlib import Path
from typing import Any

import pytest

from pyoptionpricer.market import (
    HistoricalBar,
    MarketObservation,
    OptionQuote,
    UnsupportedMarketDataCapabilityError,
)
from pyoptionpricer.market.data import MarketDataCapability, MarketDataProvider
from pyoptionpricer.market.data.providers.upstox import UpstoxMarketDataProvider


FIXTURES = Path(__file__).parents[4] / "fixtures" / "upstox"
NOW = datetime(2026, 8, 28, 12, tzinfo=UTC)
UNDERLYING_ID = "EQUITY_CASH:NSE:RELIANCE"
OPTION_ID = "EQUITY_DERIVATIVES:NSE:RELIANCE 29 SEP 26 1400 CE"


def load_json(filename: str) -> Any:
    with (FIXTURES / filename).open(encoding="utf-8") as stream:
        return json.load(stream)


class FakeUpstoxClient:
    def __init__(self) -> None:
        self.instrument_requests = 0

    def fetch_instruments(self) -> list[dict[str, Any]]:
        self.instrument_requests += 1
        return load_json("instruments.json")

    def fetch_full_quote(self, vendor_instrument_id: str) -> dict[str, Any]:
        return load_json("full_market_quote.json")

    def fetch_historical_candles(
        self, vendor_instrument_id: str, from_date: str, to_date: str
    ) -> dict[str, Any]:
        return load_json("historical_candles.json")

    def fetch_option_chain(
        self, vendor_underlying_id: str, expiry_date: str
    ) -> dict[str, Any]:
        return load_json("option_chain.json")


@pytest.fixture
def client() -> FakeUpstoxClient:
    return FakeUpstoxClient()


@pytest.fixture
def provider(client: FakeUpstoxClient) -> UpstoxMarketDataProvider:
    return UpstoxMarketDataProvider(client, clock=lambda: NOW)


def test_provider_implements_vendor_neutral_contract(
    provider: UpstoxMarketDataProvider,
) -> None:
    assert isinstance(provider, MarketDataProvider)
    assert MarketDataCapability.LIVE_QUOTE in provider.capabilities
    assert MarketDataCapability.HISTORICAL_BARS in provider.capabilities
    assert MarketDataCapability.OPTION_CHAIN in provider.capabilities


def test_live_provider_can_be_composed_from_environment() -> None:
    provider = UpstoxMarketDataProvider.from_env(
        {"UPSTOX_ACCESS_TOKEN": "short-lived-token"}, clock=lambda: NOW
    )

    assert isinstance(provider, MarketDataProvider)


def test_instrument_resolution_is_canonical_and_cached(
    provider: UpstoxMarketDataProvider, client: FakeUpstoxClient
) -> None:
    instrument = provider.get_instrument(OPTION_ID)
    matches = provider.search_instruments("reliance")

    assert instrument.instrument_id == OPTION_ID
    assert len(matches) == 2
    assert client.instrument_requests == 1


def test_instrument_resolution_accepts_vendor_instrument_keys(
    provider: UpstoxMarketDataProvider,
) -> None:
    underlying = provider.get_instrument("NSE_EQ|INE002A01018")
    option = provider.get_instrument("NSE_FO|50001")

    assert underlying.instrument_id == UNDERLYING_ID
    assert option.instrument_id == OPTION_ID


def test_quote_methods_return_only_project_owned_models(
    provider: UpstoxMarketDataProvider,
) -> None:
    spot = provider.get_underlying_quote(UNDERLYING_ID, NOW)
    option_quote = provider.get_option_quote(OPTION_ID, NOW)

    assert isinstance(spot, MarketObservation)
    assert isinstance(option_quote, OptionQuote)
    assert spot.value == pytest.approx(1387.2)
    assert option_quote.mid() == pytest.approx(35.35)


def test_generic_spot_query_accepts_canonical_symbol(
    provider: UpstoxMarketDataProvider,
) -> None:
    assert provider.get_spot("RELIANCE", NOW).value == pytest.approx(1387.2)


def test_history_returns_canonical_bars_and_close_observations(
    provider: UpstoxMarketDataProvider,
) -> None:
    start = datetime(2026, 8, 27, tzinfo=UTC)
    end = datetime(2026, 8, 29, tzinfo=UTC)

    bars = provider.get_history(UNDERLYING_ID, start, end)
    closes = provider.get_price_history(UNDERLYING_ID, start, end)

    assert all(isinstance(bar, HistoricalBar) for bar in bars)
    assert [bar.close for bar in bars] == [1375.5, 1387.2]
    assert [observation.value for observation in closes] == [1375.5, 1387.2]
    assert closes[0].source_field == "close_price"


def test_option_chain_is_normalized_before_leaving_provider(
    provider: UpstoxMarketDataProvider,
) -> None:
    chain = provider.get_option_chain(
        UNDERLYING_ID, date(2026, 9, 29), NOW
    )

    assert chain.underlying_id == UNDERLYING_ID
    assert chain.entries[0].contract_id == OPTION_ID
    assert chain.entries[0].quote.mid() == pytest.approx(35.35)
    assert chain.entries[0].vendor_implied_volatility is not None
    assert chain.entries[0].vendor_implied_volatility.value == pytest.approx(0.225)


@pytest.mark.parametrize(
    "capability",
    [
        MarketDataCapability.YIELD_CURVE,
        MarketDataCapability.DIVIDEND_DATA,
        MarketDataCapability.MARKET_DEPTH,
        MarketDataCapability.OPEN_INTEREST,
    ],
)
def test_unsupported_capabilities_fail_explicitly(
    provider: UpstoxMarketDataProvider, capability: MarketDataCapability
) -> None:
    with pytest.raises(UnsupportedMarketDataCapabilityError, match=capability.value):
        provider.require_capability(capability)


def test_unsupported_snapshot_input_fails_instead_of_using_fallback(
    provider: UpstoxMarketDataProvider,
) -> None:
    with pytest.raises(
        UnsupportedMarketDataCapabilityError, match="YIELD_CURVE"
    ):
        provider.get_yield_curve("INR", NOW)
