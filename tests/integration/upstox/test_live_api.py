"""Opt-in smoke tests for the real Upstox datasets consumed by PyOptionPricer."""

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
import os

import pytest

from pyoptionpricer import (
    CRRModelParameters,
    ContractSelection,
    MarketDataSynchronizationError,
    SingleContractValuationRequest,
    SingleContractValuationService,
)
from pyoptionpricer.market import (
    ContinuousDividendYield,
    FlatYieldCurve,
    MarketObservation,
)
from pyoptionpricer.market.data.providers.upstox import (
    HTTPUpstoxClient,
    UpstoxConfiguration,
    UpstoxMarketDataProvider,
)


pytestmark = pytest.mark.live_upstox


def _live_setting(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        pytest.skip(f"{name} is required for live Upstox tests")
    return value


def _assert_number(value: object, field: str) -> None:
    assert isinstance(value, (int, float)) and not isinstance(value, bool), (
        f"Upstox {field} must be numeric"
    )


def _live_float(name: str) -> float:
    text = _live_setting(name)
    try:
        return float(text)
    except ValueError:
        pytest.skip(f"{name} must be a decimal number")


@pytest.fixture(scope="module")
def live_client() -> HTTPUpstoxClient:
    if os.environ.get("UPSTOX_RUN_LIVE_TESTS") != "1":
        pytest.skip("set UPSTOX_RUN_LIVE_TESTS=1 to run live Upstox tests")
    _live_setting("UPSTOX_ACCESS_TOKEN")
    return HTTPUpstoxClient(UpstoxConfiguration.from_env(os.environ))


@pytest.fixture(scope="module")
def instrument_key() -> str:
    return _live_setting("UPSTOX_TEST_INSTRUMENT_KEY")


@pytest.fixture(scope="module")
def option_instrument_key() -> str:
    return _live_setting("UPSTOX_TEST_OPTION_INSTRUMENT_KEY")


def test_fetches_required_instrument_reference_data(
    live_client: HTTPUpstoxClient, instrument_key: str
) -> None:
    instruments = live_client.fetch_instruments()
    instrument = next(
        (item for item in instruments if item.get("instrument_key") == instrument_key),
        None,
    )

    assert instrument is not None, (
        f"{instrument_key!r} is absent from instrument master"
    )
    for field in (
        "instrument_key",
        "instrument_type",
        "trading_symbol",
        "exchange",
        "segment",
    ):
        assert isinstance(instrument.get(field), str) and instrument[field].strip(), (
            f"instrument master requires non-empty {field}"
        )
    assert any(
        isinstance(instrument.get(field), str) and instrument[field].strip()
        for field in ("short_name", "name", "trading_symbol")
    ), "instrument master requires a display name"


def test_fetches_required_full_quote_data(
    live_client: HTTPUpstoxClient, instrument_key: str
) -> None:
    payload = live_client.fetch_full_quote(instrument_key)
    data = payload.get("data")

    assert isinstance(data, Mapping) and data, "full quote requires a data object"
    quote = data.get(instrument_key) or data.get(instrument_key.replace("|", ":"))
    assert isinstance(quote, Mapping), "full quote requires the requested instrument"
    _assert_number(quote.get("last_price"), "last_price")
    assert quote["last_price"] > 0
    assert (
        quote.get("timestamp") is not None
        or quote.get("last_trade_time") is not None
    )


def test_fetches_required_option_quote_data(
    live_client: HTTPUpstoxClient, option_instrument_key: str
) -> None:
    payload = live_client.fetch_full_quote(option_instrument_key)
    data = payload.get("data")

    assert isinstance(data, Mapping) and data, "option quote requires a data object"
    quote = data.get(option_instrument_key) or data.get(
        option_instrument_key.replace("|", ":")
    )
    assert isinstance(quote, Mapping), "option quote requires the requested contract"
    _assert_number(quote.get("last_price"), "option last_price")
    depth = quote.get("depth")
    assert isinstance(depth, Mapping), "option quote requires market depth"
    for side in ("buy", "sell"):
        levels = depth.get(side)
        assert isinstance(levels, Sequence) and not isinstance(levels, (str, bytes))
        assert levels, f"option quote requires at least one {side} level"
        assert isinstance(levels[0], Mapping)
        _assert_number(levels[0].get("price"), f"option {side} price")


def test_fetches_required_historical_ohlcv_data(
    live_client: HTTPUpstoxClient, instrument_key: str
) -> None:
    end = datetime.now(UTC).date()
    start = end - timedelta(days=14)
    payload = live_client.fetch_historical_candles(
        instrument_key, start.isoformat(), end.isoformat()
    )
    data = payload.get("data")

    assert isinstance(data, Mapping), "historical response requires a data object"
    candles = data.get("candles")
    assert isinstance(candles, Sequence) and not isinstance(candles, (str, bytes))
    assert candles, "expected at least one daily candle in the last 14 days"
    for candle in candles:
        assert isinstance(candle, Sequence) and not isinstance(candle, (str, bytes))
        assert len(candle) >= 6, "each candle requires timestamp, OHLC, and volume"
        assert isinstance(candle[0], str) and candle[0]
        for index, field in enumerate(("open", "high", "low", "close", "volume"), 1):
            _assert_number(candle[index], field)


def test_live_single_contract_workflow_uses_synchronized_upstox_data(
    live_client: HTTPUpstoxClient,
    instrument_key: str,
    option_instrument_key: str,
) -> None:
    valuation_time = datetime.now(UTC)
    provider = UpstoxMarketDataProvider(
        live_client, clock=lambda: valuation_time
    )
    option_reference = provider.get_instrument(option_instrument_key)
    if (
        option_reference.expiry is None
        or option_reference.expiry <= valuation_time.date()
    ):
        pytest.skip("UPSTOX_TEST_OPTION_INSTRUMENT_KEY must be unexpired")

    risk_free_rate = _live_float("UPSTOX_TEST_RISK_FREE_RATE")
    dividend_yield = _live_float("UPSTOX_TEST_DIVIDEND_YIELD")
    rate_observation = MarketObservation(
        risk_free_rate,
        valuation_time,
        "LIVE_TEST_ASSUMPTION",
        "continuous_zero_rate",
    )
    dividend_observation = MarketObservation(
        dividend_yield,
        valuation_time,
        "LIVE_TEST_ASSUMPTION",
        "continuous_dividend_yield",
    )
    request = SingleContractValuationRequest(
        selection=ContractSelection(instrument_key, option_instrument_key),
        valuation_datetime=valuation_time,
        model_parameters=CRRModelParameters(200),
        yield_curve=FlatYieldCurve(risk_free_rate, rate_observation),
        dividend_data=ContinuousDividendYield(
            dividend_yield, dividend_observation
        ),
    )

    try:
        valuation = SingleContractValuationService(provider).value(request)
    except MarketDataSynchronizationError as error:
        pytest.skip(f"live market is not contemporaneous: {error}")

    assert valuation.instrument_reference == option_reference
    assert valuation.market_snapshot.spot.source == "UPSTOX"
    assert valuation.market_snapshot.option_quote.source == "UPSTOX"
    assert valuation.pricing_result.inputs.volatility.source == "UPSTOX"
    assert valuation.pricing_result.inputs.volatility.field == (
        "market_implied_volatility"
    )
    assert valuation.volatility_surface is not None
    assert valuation.used_volatility_fallback is False
    assert valuation.implied_volatility.model_price == pytest.approx(
        valuation.market_comparison.market_mid,
        abs=valuation.implied_volatility.tolerance,
    )
