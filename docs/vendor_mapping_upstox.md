# Upstox Vendor Mapping

This document records the Sprint 2 anti-corruption mapping from Upstox data
into PyOptionPricer-owned models. Upstox field names are restricted to
`pyoptionpricer.market.data.providers.upstox` and deterministic response fixtures.

## Authentication and transport

`UpstoxConfiguration.from_env()` requires `UPSTOX_ACCESS_TOKEN`. The token is
sent as an `Authorization: Bearer ...` header, is excluded from configuration
representations, and is never included in translated errors. Optional endpoint
and timeout settings are documented in `.env.example`.
The HTTP client sends an explicit `PyOptionPricer` user agent because Upstox's edge
security rejects Python `urllib`'s default browser signature.

The adapter currently uses:

- the Upstox BOD instruments JSON file;
- the v2 full-market-quote endpoint;
- the v2 put/call option-chain endpoint;
- the v3 daily historical-candle endpoint.

References:

- [Upstox authentication](https://upstox.com/developer/api-documentation/authentication/)
- [Upstox instruments](https://upstox.com/developer/api-documentation/instruments/)
- [Upstox full market quotes](https://upstox.com/developer/api-documentation/get-full-market-quote/)
- [Upstox put/call option chain](https://upstox.com/developer/api-documentation/get-pc-option-chain/)
- [Upstox historical candles V3](https://upstox.com/developer/api-documentation/v3/get-historical-candle-data/)

## Instrument mapping

| Upstox term | PyOptionPricer term | Mapping |
|---|---|---|
| `instrument_key` | `vendor_instrument_id` | Preserved as an opaque provider identifier |
| canonical segment + `exchange` + `trading_symbol` | `instrument_id` | Stable canonical identifier; vendor segment codes do not propagate |
| `trading_symbol` | `symbol` | Canonical listed symbol |
| `short_name`, then `name` | `display_symbol` | First available display value |
| `instrument_type=EQ` | `InstrumentType.EQUITY` | Explicit enum mapping |
| `instrument_type=INDEX` | `InstrumentType.INDEX` | Explicit enum mapping |
| `instrument_type=CE` | `InstrumentType.OPTION`, `OptionType.CALL` | Vendor code does not leave adapter |
| `instrument_type=PE` | `InstrumentType.OPTION`, `OptionType.PUT` | Vendor code does not leave adapter |
| `strike_price` | `strike` | Validated finite positive number |
| `expiry` | `expiry` | ISO date or epoch converted to `date` |
| `underlying_key` | `underlying_id` | Resolved through the complete instrument mapping |
| `NSE_EQ`, `BSE_EQ` | `MarketSegment.EQUITY_CASH` | Explicit segment mapping |
| `NSE_FO`, `BSE_FO` | equity/index derivatives | `underlying_type` distinguishes index options |
| `NSE_COM`, `MCX_FO` | `MarketSegment.COMMODITY_DERIVATIVES` | Commodity derivatives remain isolated from equity derivatives |

NSE, BSE, NCD, BCD, and MCX instruments are denominated as `INR` in the V1
mapping. Unknown exchanges, segments, and instrument types fail explicitly.
When the complete BOD master contains a valid but out-of-scope segment or an
inactive/unsupported instrument type, the bulk loader ignores that entry so it
cannot prevent resolution of supported instruments. Direct mapping of an
unsupported entry still fails explicitly.

## Quote mapping

| Upstox term | PyOptionPricer term |
|---|---|
| `last_price` | `last_price` or spot observation `value` |
| `depth.buy[0].price` | `bid_price` |
| `depth.sell[0].price` | `ask_price` |
| `timestamp`, fallback `last_trade_time` | canonical timezone-aware `timestamp` |
| provider identity | `source_vendor="UPSTOX"` |
| endpoint identity | `source_dataset="MARKET_QUOTE"` |

The raw quote dictionary is mapped directly to `MarketObservation` or
`OptionQuote` and cannot cross the adapter boundary.

## Option-chain and implied-volatility mapping

Each `call_options` or `put_options` object becomes a canonical
`OptionChainEntry`. Instrument keys are resolved through the normalized
instrument master; vendor option codes never leave the adapter. `bid_price`,
`ask_price`, and `ltp` become an `OptionQuote` with `OPTION_CHAIN` provenance.
`option_greeks.iv` (with the documented legacy `market_data.iv` location also
accepted) becomes `vendor_implied_volatility`. The v2 chain's percentage IV is
converted to decimal form; decimal payload variants remain decimal. Missing IV
is preserved as unavailable, while reliability policy belongs to the domain
surface rather than the Upstox mapper.

## Historical candle mapping

Upstox candle positions are mapped as follows before being returned:

| Array position | PyOptionPricer field |
|---|---|
| 0 | `timestamp` |
| 1 | `open` |
| 2 | `high` |
| 3 | `low` |
| 4 | `close` |
| 5 | `volume` |
| 6 | `open_interest` |

Every candle becomes an immutable `HistoricalBar` with `UPSTOX` and
`HISTORICAL_CANDLE` provenance. Malformed arrays, invalid OHLC relationships,
duplicates, and non-finite values raise `UpstoxPayloadError`.

## Capability limits in Sprint 2

The adapter declares instrument reference, live quote, option quote, option
chain, and historical bars. It consumes top-of-book prices while mapping an option quote,
but does not claim the broader market-depth or open-interest capabilities.
Yield-curve, dividend-data, and scalar volatility-input requests fail with
`UnsupportedMarketDataCapabilityError`; no fallback value is manufactured.

The Sprint 2 session accepts an already-issued access token. Interactive OAuth
authorization and token refresh orchestration are intentionally outside this
library boundary.
