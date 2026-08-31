from datetime import UTC, date, datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any

import pytest

from pyoptionpricer.market.data.models import InstrumentType, MarketSegment, OptionType
from pyoptionpricer.market.data.providers.upstox.errors import UpstoxPayloadError
from pyoptionpricer.market.data.providers.upstox.mapper import UpstoxMapper


FIXTURES = Path(__file__).parents[4] / "fixtures" / "upstox"
RETRIEVED_AT = datetime(2026, 8, 28, 10, 0, tzinfo=UTC)


def load_json(filename: str) -> Any:
    with (FIXTURES / filename).open(encoding="utf-8") as stream:
        return json.load(stream)


@pytest.fixture
def mapper() -> UpstoxMapper:
    return UpstoxMapper(lambda: RETRIEVED_AT)


def test_instruments_are_mapped_to_canonical_taxonomy(mapper: UpstoxMapper) -> None:
    underlying, option = mapper.map_instruments(load_json("instruments.json"))

    assert underlying.instrument_id == "EQUITY_CASH:NSE:RELIANCE"
    assert underlying.instrument_type is InstrumentType.EQUITY
    assert underlying.vendor_instrument_id == "NSE_EQ|INE002A01018"
    assert option.instrument_type is InstrumentType.OPTION
    assert option.option_type is OptionType.CALL
    assert option.strike == pytest.approx(1400.0)
    assert option.expiry == date(2026, 9, 29)
    assert option.underlying_id == underlying.instrument_id


def test_nse_commodity_segment_maps_to_commodity_derivatives(
    mapper: UpstoxMapper,
) -> None:
    instrument = mapper.map_instrument(
        {
            "segment": "NSE_COM",
            "name": "ZINC",
            "exchange": "NSE",
            "instrument_type": "FUTCOM",
            "instrument_key": "NSE_COM|ZINC26SEPFUT",
            "trading_symbol": "ZINC 25 SEP 26 FUT",
        }
    )

    assert instrument.instrument_type is InstrumentType.FUTURE
    assert instrument.segment is MarketSegment.COMMODITY_DERIVATIVES
    assert instrument.vendor_instrument_id == "NSE_COM|ZINC26SEPFUT"


def test_complete_master_ignores_valid_out_of_scope_segments(
    mapper: UpstoxMapper,
) -> None:
    instruments = mapper.map_instruments(
        [
            *load_json("instruments.json"),
            {
                "segment": "GLOBAL_INDEX",
                "name": "HANG SENG",
                "exchange": "GLOBAL",
                "instrument_type": "INDEX",
                "instrument_key": "GLOBAL_INDEX|HSI",
                "trading_symbol": "HANG SENG",
            },
        ]
    )

    assert len(instruments) == 2
    assert all(item.vendor != "GLOBAL" for item in instruments)


def test_direct_mapping_of_unsupported_segment_remains_explicit(
    mapper: UpstoxMapper,
) -> None:
    with pytest.raises(UpstoxPayloadError, match="GLOBAL_INDEX"):
        mapper.map_instrument(
            {
                "segment": "GLOBAL_INDEX",
                "name": "HANG SENG",
                "exchange": "GLOBAL",
                "instrument_type": "INDEX",
                "instrument_key": "GLOBAL_INDEX|HSI",
                "trading_symbol": "HANG SENG",
            }
        )


def test_complete_master_ignores_inactive_instrument_types(
    mapper: UpstoxMapper,
) -> None:
    instruments = mapper.map_instruments(
        [
            *load_json("instruments.json"),
            {
                "segment": "BSE_EQ",
                "name": "INACTIVE SECURITY",
                "exchange": "BSE",
                "instrument_type": "X",
                "instrument_key": "BSE_EQ|INACTIVE",
                "trading_symbol": "INACTIVE",
            },
        ]
    )

    assert len(instruments) == 2
    assert all(item.vendor_instrument_id != "BSE_EQ|INACTIVE" for item in instruments)


def test_direct_mapping_of_unsupported_instrument_type_remains_explicit(
    mapper: UpstoxMapper,
) -> None:
    with pytest.raises(UpstoxPayloadError, match="instrument_type 'X'"):
        mapper.map_instrument(
            {
                "segment": "BSE_EQ",
                "name": "INACTIVE SECURITY",
                "exchange": "BSE",
                "instrument_type": "X",
                "instrument_key": "BSE_EQ|INACTIVE",
                "trading_symbol": "INACTIVE",
            }
        )


def test_underlying_quote_is_a_provenance_bearing_observation(
    mapper: UpstoxMapper,
) -> None:
    quote = mapper.map_underlying_quote(
        load_json("full_market_quote.json"), "NSE_EQ|INE002A01018"
    )

    assert quote.value == pytest.approx(1387.2)
    assert quote.source_vendor == "UPSTOX"
    assert quote.source_dataset == "MARKET_QUOTE"
    assert quote.source_field == "last_price"
    assert quote.retrieved_at == RETRIEVED_AT


def test_option_quote_maps_depth_without_vendor_field_names(
    mapper: UpstoxMapper,
) -> None:
    quote = mapper.map_option_quote(
        load_json("full_market_quote.json"), "NSE_FO|50001"
    )

    assert quote.bid_price == pytest.approx(35.1)
    assert quote.ask_price == pytest.approx(35.6)
    assert quote.last_price == pytest.approx(35.4)
    assert quote.source_vendor == "UPSTOX"
    assert quote.source_dataset == "MARKET_QUOTE"
    assert quote.timestamp.utcoffset() == timedelta(hours=5, minutes=30)


def test_historical_candle_arrays_become_named_ordered_bars(
    mapper: UpstoxMapper,
) -> None:
    bars = mapper.map_historical_bars(load_json("historical_candles.json"))

    assert [bar.close for bar in bars] == [1375.5, 1387.2]
    assert bars[0].source_vendor == "UPSTOX"
    assert bars[0].source_dataset == "HISTORICAL_CANDLE"
    assert bars[0].retrieved_at == RETRIEVED_AT


def test_option_chain_maps_vendor_iv_to_decimal_canonical_observation(
    mapper: UpstoxMapper,
) -> None:
    instruments = mapper.map_instruments(load_json("instruments.json"))
    chain = mapper.map_option_chain(
        load_json("option_chain.json"),
        "EQUITY_CASH:NSE:RELIANCE",
        {
            instrument.vendor_instrument_id: instrument.instrument_id
            for instrument in instruments
        },
    )

    entry = chain.entries[0]
    assert entry.contract_id == (
        "EQUITY_DERIVATIVES:NSE:RELIANCE 29 SEP 26 1400 CE"
    )
    assert entry.vendor_implied_volatility is not None
    assert entry.vendor_implied_volatility.value == pytest.approx(0.225)
    assert entry.vendor_implied_volatility.source_dataset == "OPTION_CHAIN"
    assert entry.quote.mid() == pytest.approx(35.35)


def test_malformed_vendor_payload_fails_at_mapping_boundary(
    mapper: UpstoxMapper,
) -> None:
    payload = load_json("full_market_quote.json")
    payload["data"]["NSE_EQ:INE002A01018"]["last_price"] = "not-numeric"

    with pytest.raises(UpstoxPayloadError, match="last_price must be numeric"):
        mapper.map_underlying_quote(payload, "NSE_EQ|INE002A01018")
