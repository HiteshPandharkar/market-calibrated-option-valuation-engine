# PyOptionPricer --- Market-Calibrated Option Valuation Engine

## 1. Purpose

Build a production-style option pricing project that ingests real-world
market data, constructs a recombining CRR binomial tree, prices listed
vanilla options, calculates risk measures, and compares model value with
observed market prices.

This is **not** a toy pricer where users manually enter arbitrary values
such as `spot=100`, `rate=0.05`, and `volatility=0.20`.

The primary workflow must be:

``` text
Real Market Data
      ↓
Market Data Providers
      ↓
Normalized Market Snapshot
      ↓
Contract + Market Environment
      ↓
Parameter Estimation / Calibration
      ↓
PricingRequest
      ↓
CRR Tree
      ↓
Theoretical Price + Greeks + Diagnostics
      ↓
Market-vs-Model Analysis
```

The project must emphasize:

-   correctness,
-   traceability,
-   modularity,
-   testability,
-   reproducibility,
-   separation of market data from pricing logic,
-   explicit model assumptions,
-   realistic quant-pricing workflows.

------------------------------------------------------------------------

# 2. Business Problem

A derivatives desk needs to independently value an exchange-listed
option using observable market data.

Given:

-   an option contract,
-   current underlying price,
-   market option bid/ask,
-   risk-free rates,
-   dividend information,
-   volatility information,
-   valuation timestamp,

the system must:

1.  identify and construct the option contract,
2.  obtain all required market inputs,
3.  validate and normalize those inputs,
4.  construct the CRR tree parameters,
5.  calculate theoretical option value,
6.  calculate relevant sensitivities,
7.  compare theoretical value against the observed market quote,
8.  report numerical/model diagnostics,
9.  preserve the provenance of every important pricing input.

The system should answer:

> What is the theoretical value of this listed option under the selected
> CRR assumptions, what risks does it carry, and why does its model
> value differ from the observed market price?

------------------------------------------------------------------------

# 3. Initial Scope

## 3.1 Supported in V1

### Market category

-   Exchange-traded options

### Asset classes

-   Equity options
-   Index options

### Core option types

-   Call
-   Put

### Exercise styles

-   European
-   American

### Payoffs

-   Plain vanilla

### Pricing model

-   Cox-Ross-Rubinstein binomial tree

### Market inputs

-   Spot price
-   Option bid
-   Option ask
-   Option last price when available
-   Strike
-   Expiry
-   Risk-free rate / yield curve
-   Dividend yield or dividend information
-   Volatility
-   Valuation timestamp

### Outputs

-   Theoretical price
-   Market midpoint
-   Model-market difference
-   Percentage pricing difference
-   Delta
-   Gamma
-   Theta where practical
-   Tree/model diagnostics
-   Input provenance
-   Convergence analysis

------------------------------------------------------------------------

# 4. Explicitly Out of Scope for V1

Do **not** implement these before V1 is complete:

-   Asian options
-   Lookback options
-   Rainbow / multi-asset options
-   Chooser options
-   complex OTC structures
-   stochastic volatility models
-   local volatility models
-   Monte Carlo pricing
-   PDE pricing
-   Heston
-   SABR
-   automated trading
-   order execution
-   portfolio optimization

Do not prematurely generalize the system for every possible derivative.

The V1 architecture should allow later extensions without implementing
them now.

------------------------------------------------------------------------

# 5. Future Instrument Roadmap

After V1:

## V2

-   Bermudan exercise
-   Digital options
-   Barrier options

## V3

-   Entire option-chain ingestion
-   Implied volatility extraction
-   volatility smile/skew analysis
-   volatility surface construction

## V4

Introduce additional pricing engines where appropriate:

-   Monte Carlo
-   finite differences
-   Black-Scholes-Merton analytical engine

Path-dependent products such as Asian and lookback options should not be
forced into a basic recombining CRR implementation.

------------------------------------------------------------------------

# 6. Engineering Principles

Follow SOLID principles and clean architecture.

Important rules:

1.  Pricing engines must not know where market data comes from.
2.  Market-data providers must not contain pricing logic.
3.  Domain instruments must not depend on UI frameworks.
4.  Core pricing code must not depend on Streamlit.
5.  External APIs/files must be isolated behind provider interfaces.
6.  Numerical algorithms must be independently testable.
7.  Avoid global mutable state.
8.  Avoid hard-coded market assumptions.
9.  Avoid magic numbers.
10. Every external value used in pricing should have provenance where
    practical.
11. Model assumptions must be explicit.
12. Validation failures must fail clearly rather than silently
    substituting values.
13. Prefer composition and interfaces over large conditional blocks.
14. Keep domain objects independent of infrastructure.
15. Do not optimize prematurely.

------------------------------------------------------------------------

# 7. Proposed Architecture

``` text
pyoptionpricer/
│
├── src/
│   └── pyoptionpricer/
│       │
│       ├── domain/
│       │   ├── instruments/
│       │   │   ├── option.py
│       │   │   ├── european_option.py
│       │   │   └── american_option.py
│       │   │
│       │   ├── payoff/
│       │   │   └── vanilla.py
│       │   │
│       │   └── contracts/
│       │       └── option_contract.py
│       │
│       ├── market/
│       │   ├── market_environment.py
│       │   ├── snapshot.py
│       │   │
│       │   ├── data/
│       │   │   ├── provider.py
│       │   │   ├── csv_provider.py
│       │   │   └── composite_provider.py
│       │   │
│       │   ├── curves/
│       │   │   ├── yield_curve.py
│       │   │   └── dividend_curve.py
│       │   │
│       │   └── volatility/
│       │       ├── volatility_model.py
│       │       ├── historical.py
│       │       ├── ewma.py
│       │       └── implied.py
│       │
│       ├── models/
│       │   └── tree/
│       │       ├── model.py
│       │       ├── crr.py
│       │       ├── parameters.py
│       │       └── lattice.py
│       │
│       ├── pricing/
│       │   ├── requests.py
│       │   ├── results.py
│       │   ├── pricing_engine.py
│       │   ├── tree_engine.py
│       │   └── pricing_service.py
│       │
│       ├── calibration/
│       │   ├── implied_vol_solver.py
│       │   └── curve_interpolation.py
│       │
│       ├── risk/
│       │   ├── greeks.py
│       │   └── scenarios.py
│       │
│       ├── analytics/
│       │   ├── market_comparison.py
│       │   ├── convergence.py
│       │   └── arbitrage_checks.py
│       │
│       └── diagnostics/
│           └── pricing_diagnostics.py
│
├── app/
│   └── streamlit/
│
├── data/
│   ├── raw/
│   ├── normalized/
│   └── samples/
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── regression/
│
├── docs/
│
├── pyproject.toml
└── README.md
```

If integrating this work into an existing pricing library, adapt this
structure rather than duplicating already-correct abstractions.

------------------------------------------------------------------------

# 8. Core Domain Model

## 8.1 OptionContract

Create an immutable representation of the exchange contract.

Suggested fields:

``` python
OptionContract(
    underlying: str,
    strike: float,
    expiry: date,
    option_type: OptionType,
    exercise_style: ExerciseStyle,
    asset_class: AssetClass,
    exchange: str | None,
    contract_symbol: str | None,
    currency: Currency,
)
```

Validation:

-   strike \> 0
-   expiry must be valid
-   underlying cannot be empty
-   option type must be valid
-   exercise style must be supported

Do not store live market prices in `OptionContract`.

Contract definition and market state are separate concepts.

------------------------------------------------------------------------

# 9. Market Data Abstraction

Define an abstract market-data interface.

Example:

``` python
class MarketDataProvider(ABC):

    @abstractmethod
    def get_spot(self, symbol, timestamp):
        ...

    @abstractmethod
    def get_option_quote(self, contract, timestamp):
        ...

    @abstractmethod
    def get_price_history(self, symbol, start, end):
        ...

    @abstractmethod
    def get_yield_curve(self, currency, timestamp):
        ...

    @abstractmethod
    def get_dividend_data(self, symbol, timestamp):
        ...
```

Do not couple the rest of the application to one website, API, vendor,
CSV schema, or exchange endpoint.

------------------------------------------------------------------------

# 10. Provider Strategy


## 10.1 Initial Integration Priority: Upstox

The first live/vendor integration for this project must be **Upstox**.

However, Upstox must be implemented strictly as an infrastructure adapter behind project-owned interfaces.

The rest of the system must not depend on Upstox field names, identifiers, enums, response objects, authentication types, expiry formats, option-chain schemas, or quote schemas.

```text
Application / Pricing Core
            │
            ▼
 Project Market Data Interfaces
            │
            ▼
   Provider Adapter Layer
            │
    ┌───────┼────────┐
    ▼       ▼        ▼
 Upstox   FYERS    Dhan
 initial  future    future
```

For V1, `UpstoxMarketDataProvider` is the first implementation of the vendor-neutral project interfaces.

Vendor-specific names must exist only inside the Upstox adapter package.

Bad:
`UpstoxOption`, `UpstoxQuote`, `UpstoxInstrument`

Preferred:
`OptionContract`, `OptionQuote`, `InstrumentReference`, `MarketSnapshot`

---

## 10.2 Upstox Integration Responsibilities

The Upstox adapter is responsible for authentication/session handling, instrument resolution, underlying quotes, option-chain retrieval, individual option quotes where required, historical candles, canonical mapping, and translating vendor errors into project-level provider errors.

It must return project-owned models such as:

`InstrumentReference`, `UnderlyingQuote`, `OptionQuote`, `HistoricalBar`, `OptionChain`, `MarketObservation`

Raw dictionaries must not cross the infrastructure boundary.

---

## 10.3 Upstox Provider Decomposition

Suggested structure:

```text
market/
└── data/
    ├── provider.py
    ├── models.py
    ├── normalization.py
    └── providers/
        └── upstox/
            ├── client.py
            ├── auth.py
            ├── mapper.py
            ├── provider.py
            ├── errors.py
            └── schemas.py
```

Responsibilities:

- `client.py`: HTTP/API communication only
- `schemas.py`: vendor response models if required
- `mapper.py`: Upstox → project canonical taxonomy
- `provider.py`: implements project provider interfaces
- `auth.py`: token/session handling
- `errors.py`: vendor failure → project provider error

Do not mix HTTP calls, parsing, mapping, pricing logic, and business rules in one class.

---

## 10.4 Provider Capability Model

Different vendors may expose different datasets.

Define capabilities explicitly.

```python
class MarketDataCapability(Enum):
    LIVE_QUOTE = ...
    OPTION_CHAIN = ...
    HISTORICAL_BARS = ...
    OPTION_QUOTE = ...
    INSTRUMENT_REFERENCE = ...
    MARKET_DEPTH = ...
    OPEN_INTEREST = ...
```

Application logic must fail clearly when a requested capability is unsupported.

Do not emulate unavailable capabilities silently.

---

## 10.5 Vendor-Neutral Provider Interfaces

Prefer focused interfaces:

```python
class InstrumentReferenceProvider(ABC):
    def get_instrument(...)
    def search_instruments(...)

class QuoteProvider(ABC):
    def get_underlying_quote(...)
    def get_option_quote(...)

class OptionChainProvider(ABC):
    def get_option_chain(...)

class HistoricalPriceProvider(ABC):
    def get_history(...)
```

A composed `MarketDataProvider` may expose several capabilities.

The architectural requirement is separation of responsibilities, not a rigid inheritance hierarchy.

---

## 10.6 Canonical Project Taxonomy

The project must define its own canonical vocabulary.

Vendor terminology must be translated into this taxonomy before reaching application, domain, pricing, storage, logging, testing, or UI code.

The project taxonomy is the source of truth.

Vendor terminology may appear only in provider-specific mapping/provenance contexts.

---

## 10.7 Canonical Taxonomy — Instruments

```text
Instrument
│
├── Underlying
│   ├── Equity
│   └── Index
│
└── Option
    ├── Call
    └── Put
```

Canonical fields:

```text
instrument_id
instrument_type
underlying_id
symbol
display_symbol
exchange
segment
currency
```

Option fields:

```text
option_type
exercise_style
strike
expiry
underlying_id
contract_id
```

Vendor terms such as `instrument_key`, `security_id`, `token`, `tradingsymbol`, and `exchange_token` must not propagate outside adapters.

Use project fields such as:

```text
instrument_id
vendor_instrument_id
```

---

## 10.8 Canonical Taxonomy — Market Segments

Suggested canonical values:

```text
EQUITY_CASH
EQUITY_DERIVATIVES
INDEX_DERIVATIVES
CURRENCY_DERIVATIVES
COMMODITY_DERIVATIVES
```

Vendor codes such as `NSE_EQ`, `NSE_FO`, `NFO`, or `FO` must be mapped internally.

---

## 10.9 Canonical Taxonomy — Option Types

Use:

```text
CALL
PUT
```

Do not expose vendor encodings such as:

```text
CE
PE
C
P
```

Map them to:

```python
OptionType.CALL
OptionType.PUT
```

---

## 10.10 Canonical Taxonomy — Exercise Styles

Use:

```text
EUROPEAN
AMERICAN
BERMUDAN
```

Where a vendor does not provide exercise style directly, resolve it using project instrument metadata/rules and record the source of that classification.

---

## 10.11 Canonical Taxonomy — Quote Fields

Use:

```text
bid_price
ask_price
last_price
open_price
high_price
low_price
close_price
volume
open_interest
timestamp
```

Vendor abbreviations such as `ltp`, `oi`, `cp`, `lp` must remain inside vendor schemas/mappers.

---

## 10.12 Canonical Taxonomy — Historical Bars

Use:

```python
HistoricalBar(
    timestamp=...,
    open=...,
    high=...,
    low=...,
    close=...,
    volume=...,
    open_interest=...,
)
```

Do not bind the rest of the application to vendor candle-array ordering.

---

## 10.13 Canonical Taxonomy — Option Chain

Define project-owned objects:

```python
OptionChain(
    underlying=...,
    expiry=...,
    spot=...,
    strikes=[...],
)
```

```python
OptionChainStrike(
    strike=...,
    call=OptionMarketEntry(...),
    put=OptionMarketEntry(...),
)
```

Each option market entry may include:

```text
contract
bid_price
ask_price
last_price
volume
open_interest
vendor_implied_volatility
timestamp
```

Keep `vendor_implied_volatility` distinct from `model_implied_volatility`.

Never store both under an ambiguous field like `iv`.

---

## 10.14 Canonical Taxonomy — Volatility

Use explicit names:

```text
historical_volatility
ewma_volatility
vendor_implied_volatility
model_implied_volatility
```

Definitions:

- `historical_volatility`: estimated from historical underlying returns
- `ewma_volatility`: estimated using EWMA
- `vendor_implied_volatility`: supplied by an external provider
- `model_implied_volatility`: solved by this project so model price equals the selected market target price

Pricing configuration should explicitly contain:

```text
volatility_source
volatility_value
```

---

## 10.15 Canonical Taxonomy — Prices

Distinguish:

```text
market_bid
market_ask
market_mid
market_last
market_close
market_settlement

model_price
intrinsic_value
continuation_value
exercise_value
```

Avoid a generic `price` field when context is ambiguous.

---

## 10.16 Canonical Taxonomy — Identifiers

Separate internal and vendor identifiers.

```python
InstrumentReference(
    instrument_id=...,
    vendor="UPSTOX",
    vendor_instrument_id=...,
    symbol=...,
    exchange=...,
)
```

Rules:

- `instrument_id` is project-owned/normalized
- `vendor_instrument_id` is opaque
- never parse business meaning from opaque vendor IDs outside adapters
- never expose vendor IDs as user-facing names
- preserve them only for provider calls and provenance

---

## 10.17 Canonical Taxonomy — Time

Use explicit concepts:

```text
valuation_datetime
market_timestamp
quote_timestamp
bar_timestamp
expiry_datetime
```

All timestamps must have clear timezone semantics.

Normalize vendor timestamps at the provider boundary.

---

## 10.18 Canonical Taxonomy — Provenance

Every normalized observation should support:

```text
source_vendor
source_dataset
source_field
source_timestamp
retrieved_at
```

Example:

```text
source_vendor      = UPSTOX
source_dataset     = OPTION_CHAIN
source_field       = last_price
```

The UI may display `Source: Upstox` as provenance only.

---

## 10.19 Vendor Mapping Documentation

Maintain:

```text
docs/vendor_mapping_upstox.md
```

The document must map real Upstox terminology to project terminology.

Example:

| Upstox Term | Project Canonical Term | Notes |
|---|---|---|
| instrument_key | vendor_instrument_id | Opaque provider identifier |
| CE | CALL | Normalize to OptionType.CALL |
| PE | PUT | Normalize to OptionType.PUT |
| ltp | last_price | Quote field |
| oi | open_interest | Quote/option field |
| candle | HistoricalBar | Positional payload → named fields |

Populate the final mapping from verified Upstox schemas. Do not guess undocumented mappings.

---

## 10.20 Anti-Corruption Layer

Treat each vendor adapter as an anti-corruption layer:

```text
UPSTOX LANGUAGE
       ↓
Upstox Mapper
       ↓
PROJECT LANGUAGE
       ↓
Entire application
```

Never allow:

```text
UPSTOX LANGUAGE
       ↓
Pricing Engine
```

---

## 10.21 Provider Switching

Provider selection must be configuration-driven.

```text
market_data_provider = "upstox"
```

Later:

```text
market_data_provider = "fyers"
market_data_provider = "dhan"
market_data_provider = "csv"
```

Use a registry, factory, or dependency-injection mechanism.

---

## 10.22 Provider Fallback

Do not automatically combine/fallback across vendors in V1.

Hidden fallback can produce inconsistent snapshots, e.g. spot from vendor A and option price from vendor B at different timestamps.

If fallback is introduced later, provenance must be preserved for every input independently.

---

## 10.23 Upstox Authentication

Requirements:

- no access tokens committed to source control
- no secrets in tests
- use environment variables or secure local configuration
- provide `.env.example`
- redact credentials from logs
- expose authentication failures as explicit provider errors

The pricing engine must have no concept of access tokens.

---

## 10.24 Raw Response Retention

Allow optional raw-response persistence:

```text
data/raw/upstox/
```

Use only for debugging, reproducibility, schema-change investigation, and mapping tests.

Pricing code must always consume normalized objects.

---

## 10.25 Upstox Contract Tests

Create local fixtures:

```text
tests/fixtures/upstox/
    instrument.json
    quote.json
    option_chain.json
    historical_candles.json
```

Tests should verify canonical mappings without requiring network access.

---

## 10.26 Initial Upstox End-to-End Target

```text
Canonical contract selection
        ↓
Upstox adapter
        ↓
Instrument resolution
        ↓
Underlying quote
        ↓
Option chain / option quote
        ↓
Historical underlying data
        ↓
Canonical MarketSnapshot
        ↓
Volatility estimation
        ↓
CRR PricingRequest
        ↓
PricingResult
```

The CRR engine must not know which vendor supplied the data.

Switching vendors later must require changes only in configuration and provider-specific adapter code.


Implement providers incrementally.

## First provider

Implement:

``` text
CSVMarketDataProvider
```

Use reproducible historical/sample files.

This allows the entire pricing pipeline to be tested without network
dependency.

## Later providers

Possible implementations:

``` text
MarketDataProvider
│
├── CSVMarketDataProvider
├── UnderlyingMarketDataProvider
├── ExchangeFileProvider
├── RateProvider
└── CompositeMarketDataProvider
```

`CompositeMarketDataProvider` may combine different sources:

``` text
Underlying quote      → Provider A
Option contract       → Provider B
Option quote          → Provider B
Yield curve           → Provider C
Dividend data         → Provider D
```

Do not implement brittle web scraping in the pricing core.

------------------------------------------------------------------------

# 11. Market Data Provenance

Every important market observation should support metadata such as:

``` python
MarketObservation(
    value=...,
    timestamp=...,
    source=...,
    field=...,
)
```

Example:

``` text
spot
value       = 1387.20
timestamp   = 2026-08-28 15:29:00
source      = exchange_file
field       = close
```

The final report should make it possible to determine where each pricing
input originated.

------------------------------------------------------------------------

# 12. Market Snapshot

Create a normalized `MarketSnapshot`.

Suggested conceptual structure:

``` python
MarketSnapshot(
    valuation_datetime=...,
    spot=...,
    option_quote=...,
    yield_curve=...,
    dividend_data=...,
    volatility_input=...,
)
```

The pricing engine receives normalized market objects.

It must never parse raw CSV rows, JSON responses, or API payloads.

------------------------------------------------------------------------

# 13. Quote Model

Represent option quotes explicitly.

Example:

``` python
OptionQuote(
    bid: float | None,
    ask: float | None,
    last: float | None,
    timestamp: datetime,
)
```

Provide:

``` python
mid()
```

Rules:

-   if bid and ask are valid, midpoint = `(bid + ask) / 2`
-   never silently use zero for missing bid/ask
-   reject negative prices
-   detect crossed markets where `bid > ask`
-   report stale or incomplete quotes through diagnostics

------------------------------------------------------------------------

# 14. Yield Curve

Do not hard-code a constant `r = 0.05`.

Create a yield-curve abstraction.

Example:

``` python
class YieldCurve(ABC):

    def zero_rate(self, maturity):
        ...

    def discount_factor(self, maturity):
        ...
```

The CRR request should obtain the rate corresponding to option maturity.

Initially a simple interpolated zero curve is sufficient.

Document:

-   compounding convention,
-   day-count convention,
-   interpolation method.

------------------------------------------------------------------------

# 15. Dividend Treatment

Support:

``` text
q = continuous dividend yield
```

for V1.

Keep dividend handling behind an abstraction so discrete dividends can
be introduced later.

The pricing model should use the cost-of-carry term:

``` text
r - q
```

where appropriate.

------------------------------------------------------------------------

# 16. Volatility Architecture

Create:

``` python
class VolatilityModel(ABC):

    def estimate(...):
        ...
```

Initial implementations:

``` text
VolatilityModel
│
├── HistoricalVolatility
├── EWMAVolatility
└── ImpliedVolatility
```

Later:

``` text
VolSurfaceInterpolator
```

------------------------------------------------------------------------

# 17. Historical Volatility

Implement annualized historical volatility using log returns.

Conceptually:

``` text
r_t = ln(S_t / S_(t-1))

sigma_daily = std(r_t)

sigma_annual = sigma_daily * sqrt(trading_days)
```

Do not hide assumptions.

Make configurable:

-   lookback period,
-   annualization factor,
-   return convention.

------------------------------------------------------------------------

# 18. EWMA Volatility

Implement EWMA as an alternative volatility estimator.

The decay factor must be configurable.

Do not hard-code a value without documenting it.

Add tests verifying the recursive variance calculation.

------------------------------------------------------------------------

# 19. Implied Volatility Solver

Implement an implied-volatility solver using the CRR engine.

Solve:

``` text
CRRPrice(sigma) - MarketMid = 0
```

Inputs:

-   contract,
-   market snapshot,
-   target market price,
-   tree steps.

Use a robust root-finding method such as bisection or Brent where
available.

Requirements:

-   configurable volatility bounds,
-   convergence tolerance,
-   maximum iterations,
-   explicit failure result,
-   no silent fallback.

Return a structured result:

``` python
ImpliedVolResult(
    volatility=...,
    converged=True,
    iterations=...,
    pricing_error=...,
)
```

------------------------------------------------------------------------

# 20. CRR Model

For:

``` text
dt = T / N
```

use:

``` text
u = exp(sigma * sqrt(dt))

d = exp(-sigma * sqrt(dt))
```

and risk-neutral probability:

``` text
p = (exp((r - q) * dt) - d) / (u - d)
```

Discount one step using the selected rate convention.

Validate:

``` text
0 <= p <= 1
```

and relevant no-arbitrage conditions.

Do not continue pricing if parameters produce an invalid tree unless the
API explicitly returns a failed diagnostic result.

------------------------------------------------------------------------

# 21. Tree Construction

Separate:

``` text
CRR parameter calculation
```

from:

``` text
lattice construction
```

from:

``` text
backward induction
```

Suggested components:

``` text
CRRTreeParameters
CRRTreeBuilder
Lattice
TreePricingEngine
```

Avoid one giant class containing:

-   validation,
-   tree construction,
-   payoff calculation,
-   Greeks,
-   reporting,
-   market data retrieval.

------------------------------------------------------------------------

# 22. European Exercise

At maturity:

``` text
Call = max(S_T - K, 0)

Put = max(K - S_T, 0)
```

At earlier nodes:

``` text
V = discount * (
    p * V_up +
    (1 - p) * V_down
)
```

No early exercise.

------------------------------------------------------------------------

# 23. American Exercise

At every eligible node calculate:

``` text
continuation_value
```

and:

``` text
intrinsic_value
```

Then:

``` text
V = max(
    continuation_value,
    intrinsic_value,
)
```

Record early-exercise information where useful for diagnostics.

Exercise policy should be separate from the generic tree mechanics.

------------------------------------------------------------------------

# 24. PricingRequest

The pricing engine should receive a complete request object.

Example:

``` python
PricingRequest(
    instrument=option,
    market=market_environment,
    model_parameters=CRRModelParameters(
        steps=500,
    ),
)
```

Do not design the public pricing API around:

``` python
price(
    spot=100,
    strike=105,
    rate=0.05,
    volatility=0.20,
)
```

The engine should consume domain objects.

------------------------------------------------------------------------

# 25. PricingResult

Return structured output.

Suggested fields:

``` python
PricingResult(
    price=...,
    currency=...,
    greeks=...,
    diagnostics=...,
    model_name="CRR",
    model_parameters=...,
    valuation_datetime=...,
)
```

Do not return only a float.

------------------------------------------------------------------------

# 26. Greeks

V1 should provide:

-   Delta
-   Gamma
-   Theta where stable/practical

Prefer extracting tree-based Greeks where mathematically appropriate.

Document exactly how each sensitivity is calculated.

Do not report a Greek without defining:

-   bump convention if finite differences are used,
-   units,
-   sign,
-   numerical method.

------------------------------------------------------------------------

# 27. Market Comparison

Create a separate analytics component.

Example:

``` python
MarketComparison(
    market_bid=...,
    market_ask=...,
    market_mid=...,
    model_price=...,
    absolute_difference=...,
    percentage_difference=...,
)
```

The pricing engine calculates theoretical value.

The analytics layer compares it with the market.

Do not mix these responsibilities.

------------------------------------------------------------------------

# 28. Convergence Analysis

Implement CRR convergence analysis.

Example step counts:

``` text
10
25
50
100
250
500
1000
```

Return:

``` text
steps     price
10        ...
25        ...
50        ...
...
```

The system should detect whether increasing tree resolution produces a
sufficiently stable price.

Do not assume that a large number of steps automatically guarantees a
valid result.

------------------------------------------------------------------------

# 29. Diagnostics

Create structured diagnostics.

Possible checks:

``` text
Contract validation                 PASS/FAIL
Market quote validity               PASS/FAIL
Quote freshness                     PASS/WARN
Yield curve availability            PASS/FAIL
Volatility availability             PASS/FAIL
Risk-neutral probability            PASS/FAIL
No-arbitrage condition              PASS/FAIL
Tree convergence                    PASS/WARN/FAIL
Implied-vol convergence             PASS/FAIL
```

Diagnostics should be machine-readable, not only strings printed to
stdout.

------------------------------------------------------------------------

# 30. Final Pricing Report

A typical report should resemble:

``` text
RELIANCE SEP-2026 1400 CALL
────────────────────────────────────

CONTRACT

Underlying                  RELIANCE
Strike                      1400
Expiry                      2026-09-24
Option Type                 CALL
Exercise                    EUROPEAN

MARKET

Spot                        1387.20
Bid                         35.10
Ask                         35.60
Mid                         35.35

MODEL

Model                       CRR
Steps                       500
Risk-Free Rate              5.47%
Dividend Yield              0.31%
Volatility                  21.84%

VALUATION

Theoretical Price           34.82
Market Mid                  35.35
Difference                  -0.53
Difference %                -1.50%

RISK

Delta                       ...
Gamma                       ...
Theta                       ...

DIAGNOSTICS

Risk-neutral probability    PASS
No-arbitrage                PASS
Tree convergence            PASS
Market quote                PASS
```

All example numbers above are placeholders.

Never hard-code them into production logic.

------------------------------------------------------------------------

# 31. Option Chain Extension

After single-contract V1 works, add option-chain processing.

For every contract:

``` text
Strike
Option Type
Bid
Ask
Mid
Model Price
Absolute Error
Percentage Error
Implied Volatility
```

Example output schema:

``` text
strike | market_mid | model_price | error_pct | implied_vol
```

The pipeline should reuse the same single-contract pricing service
rather than implementing a second pricing system.

------------------------------------------------------------------------

# 32. Volatility Smile

Using option-chain prices:

1.  calculate market midpoint,
2.  solve implied volatility independently for each strike,
3.  store strike and IV,
4.  visualize:

``` text
strike → implied volatility
```

This should demonstrate why a single constant volatility cannot
generally reproduce an entire observed option chain.

------------------------------------------------------------------------

# 33. Data Quality

Before pricing, validate:

-   missing values,
-   duplicate records,
-   negative prices,
-   zero/invalid strike,
-   expiry before valuation,
-   bid \> ask,
-   stale timestamps,
-   missing rates,
-   insufficient historical observations,
-   non-positive underlying prices,
-   malformed contract identifiers.

Do not silently clean serious errors.

Return explicit validation errors or warnings.

------------------------------------------------------------------------

# 34. Reproducibility

A valuation must be reproducible.

Given:

``` text
contract
valuation timestamp
market snapshot
model configuration
```

the system should produce the same result.

Store enough information to reproduce historical pricing runs.

Avoid relying on "latest market value" deep inside the pricing engine.

------------------------------------------------------------------------

# 35. Logging

Log important workflow events:

``` text
market snapshot created
contract resolved
volatility estimated
yield selected/interpolated
pricing started
pricing completed
diagnostic failure
IV calibration completed
```

Do not log enormous lattice structures by default.

Do not use print statements as the logging system.

------------------------------------------------------------------------

# 36. Error Handling

Use domain-specific exceptions or structured failures where appropriate.

Examples:

``` text
InvalidContractError
MarketDataUnavailableError
InvalidMarketQuoteError
CurveInterpolationError
InvalidTreeParametersError
CalibrationError
PricingError
```

Never use:

``` python
except Exception:
    return None
```

for core pricing workflows.

------------------------------------------------------------------------

# 37. Testing Strategy

Testing is mandatory.

## Unit tests

Test independently:

-   vanilla payoff,
-   contract validation,
-   midpoint calculation,
-   historical volatility,
-   EWMA volatility,
-   yield interpolation,
-   CRR parameter calculation,
-   risk-neutral probability,
-   lattice construction,
-   European backward induction,
-   American exercise logic,
-   implied-vol root solver,
-   market comparison,
-   convergence analysis.

## Integration tests

Test:

``` text
raw/sample market data
        ↓
provider
        ↓
market snapshot
        ↓
pricing request
        ↓
CRR engine
        ↓
pricing result
```

## Regression tests

Use fixed market snapshots.

Persist expected results within documented numerical tolerances.

A provider/API change must not silently alter model behavior.

------------------------------------------------------------------------

# 38. Reference Tests

Where assumptions align, compare European CRR results against a
Black-Scholes-Merton reference implementation.

Expected behavior:

``` text
CRR price → BSM price
```

as the number of steps increases.

Use tolerance-based assertions.

Do not require exact floating-point equality.

For American options, use independently verified benchmark cases.

------------------------------------------------------------------------

# 39. Performance

Correctness comes before optimization.

After correctness:

measure:

-   tree construction time,
-   pricing time,
-   option-chain pricing time,
-   memory usage as steps increase.

Avoid optimizing based on guesses.

Add benchmarks only after V1 correctness is established.

------------------------------------------------------------------------

# 40. UI

The UI is not the architecture.

Implement UI only after the core workflow works through Python/tests.

Suggested UI flow:

``` text
Select underlying
        ↓
Select expiry
        ↓
Select strike
        ↓
Select call/put
        ↓
Select volatility source
        ↓
Select tree steps
        ↓
PRICE
```

Display:

-   contract,
-   market snapshot,
-   model assumptions,
-   theoretical value,
-   market quote,
-   pricing difference,
-   Greeks,
-   diagnostics,
-   convergence,
-   data provenance.

Keep Streamlit-specific code outside the core package.

------------------------------------------------------------------------

# 41. CLI / Programmatic Workflow

Before UI development, support a simple programmatic or CLI workflow.

Conceptually:

``` text
price-option
    --symbol ...
    --expiry ...
    --strike ...
    --type ...
    --valuation-time ...
    --steps ...
    --volatility-source ...
```

The command should call application services rather than contain pricing
logic.

------------------------------------------------------------------------

# 42. Implementation Sprints

Codex must implement the project incrementally.

Do **not** attempt the entire project in one change.

Each sprint must:

1.  inspect the existing code,
2.  state the proposed changes,
3.  implement only that sprint,
4.  add/update tests,
5.  run the relevant test suite,
6.  fix failures caused by the sprint,
7.  summarize changed files,
8.  stop before beginning the next sprint.

Do not proceed automatically through all sprints in one response/change
set unless explicitly instructed.

------------------------------------------------------------------------

# 43. Sprint 0 --- Existing Code Assessment

Before changing code:

1.  inspect the repository,
2.  identify existing:
    -   instruments,
    -   payoffs,
    -   pricing requests,
    -   pricing results,
    -   engine registry,
    -   CRR engine,
    -   market environment,
    -   curve abstractions,
    -   volatility abstractions,
    -   tests,
3.  map existing components to this specification,
4.  identify reusable code,
5.  identify missing abstractions,
6.  identify technical debt that blocks this project.
7.  assess existing vendor-integration code and dependencies, including any Upstox client, authentication, instrument-resolution, quote, option-chain, or historical-data code.
8.  identify the minimum changes required to place Upstox behind the project-owned provider interfaces and canonical taxonomy.

Output:

``` text
docs/pyoptionpricer_gap_analysis.md
```

Do not rewrite functioning architecture merely to match folder names in
this document.

------------------------------------------------------------------------

# 44. Sprint 1 --- Market Data Domain

Implement:

-   `MarketObservation`
-   `OptionQuote`
-   `MarketSnapshot`
-   validation
-   provenance metadata

Implement tests.

Acceptance criteria:

-   valid quote midpoint works,
-   crossed markets are detected,
-   negative prices rejected,
-   missing values handled explicitly,
-   timestamps preserved,
-   provenance accessible.
-   normalized market objects can carry vendor provenance without exposing vendor-specific field names.

------------------------------------------------------------------------

# 45. Sprint 2 --- Market Data Provider

Implement:

-   `MarketDataProvider`
-   `CSVMarketDataProvider`
-   sample data fixtures
-   vendor-neutral provider capability interfaces required by the Upstox adapter
-   `UpstoxMarketDataProvider` adapter package
-   Upstox authentication/session handling using environment-based configuration
-   Upstox instrument-reference retrieval and canonical instrument mapping
-   Upstox underlying quote retrieval and canonical quote mapping
-   Upstox historical-candle retrieval and canonical `HistoricalBar` mapping
-   provider-level error translation for Upstox failures
-   local Upstox response fixtures for mapping and contract tests
-   `docs/vendor_mapping_upstox.md`

The CSV provider must support enough data to build a complete V1 market
snapshot.

Acceptance criteria:

-   pricing code contains no CSV parsing,
-   malformed rows produce clear errors,
-   provider tests use deterministic fixtures,
-   snapshot construction works without internet access.
-   Upstox-specific identifiers, enums, schemas, and response objects do not cross the adapter boundary,
-   raw Upstox dictionaries do not reach domain, pricing, analytics, storage, or UI code,
-   Upstox mapping tests run without network access,
-   authentication secrets are not committed or logged,
-   unsupported provider capabilities fail explicitly.

------------------------------------------------------------------------

# 46. Sprint 3 --- Yield and Dividend Inputs

Implement:

-   yield-curve abstraction if absent,
-   interpolation,
-   continuous dividend-yield support,
-   required conventions.

Acceptance criteria:

-   maturity-specific rate can be requested,
-   interpolation tested,
-   invalid maturities handled,
-   no hard-coded risk-free rate in CRR workflow.

------------------------------------------------------------------------

# 47. Sprint 4 --- Volatility Estimation

Implement:

-   `VolatilityModel`
-   historical volatility
-   EWMA volatility

Acceptance criteria:

-   log returns used correctly,
-   annualization documented,
-   lookback configurable,
-   EWMA decay configurable,
-   insufficient history rejected,
-   deterministic tests included.
-   historical volatility and EWMA volatility can consume normalized historical bars returned by the Upstox adapter without vendor-specific logic.

------------------------------------------------------------------------

# 48. Sprint 5 --- CRR Market Integration

Connect:

``` text
OptionContract
+
MarketSnapshot
+
CRRModelParameters
        ↓
PricingRequest
        ↓
CRR Engine
```

Acceptance criteria:

-   no raw provider payload reaches CRR,
-   `r`, `q`, `sigma`, `S`, `T` are traceable,
-   European call and put supported,
-   American call and put supported where appropriate,
-   invalid risk-neutral probabilities detected,
-   result is structured.
-   a normalized `MarketSnapshot` built from Upstox underlying/option market observations can be passed into the same CRR workflow used by the CSV provider,
-   switching between CSV and Upstox requires configuration/provider selection only,
-   the CRR engine contains no Upstox imports or vendor-specific conditionals.

------------------------------------------------------------------------

# 49. Sprint 6 --- Greeks

Implement:

-   Delta
-   Gamma
-   Theta

Acceptance criteria:

-   formulas/method documented,
-   units documented,
-   benchmark tests,
-   numerical instability handled explicitly.

------------------------------------------------------------------------

# 50. Sprint 7 --- Market Comparison

Implement:

-   market midpoint,
-   absolute pricing difference,
-   percentage difference,
-   market comparison result.
-   Upstox option bid/ask/last fields are mapped into the canonical `OptionQuote` before comparison.

Acceptance criteria:

``` text
model price
market bid
market ask
market mid
absolute difference
percentage difference
```

are available independently of the UI.
-   market comparison produces identical application-level output structure regardless of whether the normalized quote originated from CSV or Upstox.

------------------------------------------------------------------------

# 51. Sprint 8 --- Convergence and Diagnostics

Implement:

-   convergence runner,
-   no-arbitrage checks,
-   risk-neutral probability checks,
-   data-quality diagnostics,
-   structured diagnostic statuses.
-   provider diagnostics for Upstox authentication failure, unavailable data, malformed payloads, stale quotes, and unsupported capabilities.

Acceptance criteria:

-   multiple step counts can be evaluated,
-   convergence results are stored,
-   invalid model states cannot masquerade as valid prices.

------------------------------------------------------------------------

# 52. Sprint 9 --- Implied Volatility

Implement:

``` text
market midpoint
        ↓
CRR pricing function
        ↓
root solver
        ↓
implied volatility
```

Acceptance criteria:

-   known synthetic IV can be recovered,
-   convergence tolerance configurable,
-   failure is explicit,
-   iteration count returned,
-   pricing residual returned.
-   implied-volatility calibration accepts normalized Upstox option quotes through the same market-midpoint interface used by other providers.

------------------------------------------------------------------------

# 53. Sprint 10 --- End-to-End Single Contract

Implement the complete workflow:

``` text
vendor option chain
        ↓
normalized vendor implied volatilities
        ↓
contract resolution
        ↓
market IV surface construction/interpolation
        ↓
contract strike/expiry IV selection
        ↓
normalized market snapshot
        ↓
pricing request
        ↓
CRR pricing
        ↓
Greeks
        ↓
market comparison
        ↓
diagnostics
```

Acceptance criteria:

A single command/test can reproduce an entire valuation from stored
raw/sample data.

Add an Upstox-backed end-to-end integration path:

``` text
canonical contract selection
        ↓
Upstox adapter
        ↓
instrument resolution
        ↓
underlying quote
        ↓
put/call option chain and vendor IV
        ↓
normalized market IV surface
        ↓
contract strike/expiry IV selection
        ↓
CRR up/down factors and risk-neutral probability
        ↓
pricing request
        ↓
CRR pricing
        ↓
Greeks
        ↓
market comparison
        ↓
diagnostics
```

Additional acceptance criteria:

-   the Upstox-backed workflow uses the same application and pricing services as the CSV-backed workflow,
-   no Upstox response object reaches the pricing engine,
-   every Upstox-derived pricing input retains provenance,
-   the selected market-surface IV drives CRR parameters and theoretical price,
-   the theoretical price is compared with market bid, ask, and midpoint,
-   historical or EWMA volatility is used only as an explicitly configured fallback when reliable market IV is unavailable,
-   option-chain and surface domain models remain vendor-independent,
-   provider selection is configuration-driven,
-   an Upstox integration test is separated from deterministic offline tests and can be skipped when credentials/network access are unavailable.

------------------------------------------------------------------------

# 54. Sprint 11 --- Streamlit UI

Only begin after Sprint 10 passes.

Implement a thin UI over application services.

Do not duplicate:

-   validation,
-   pricing,
-   volatility estimation,
-   market comparison,
-   calibration

inside Streamlit pages.

Add:

-   provider selection through application configuration,
-   Upstox-backed contract lookup using canonical project terminology,
-   clear display of provider/authentication/data-availability failures without exposing credentials or raw vendor payloads,
-   source provenance display such as `Source: Upstox` without exposing vendor-specific identifiers as user-facing names.

------------------------------------------------------------------------

# 55. Sprint 12 --- Option Chain

Add batch processing.

Add Upstox option-chain integration:

-   retrieve the option chain through the Upstox adapter,
-   map every returned strike, call, put, quote, open-interest value, timestamp, and vendor IV into the canonical `OptionChain` model,
-   keep `vendor_implied_volatility` separate from `model_implied_volatility`,
-   reuse the same batch-processing pipeline for normalized chains regardless of provider.

Acceptance criteria:

-   process multiple strikes,
-   reuse single-contract pricing pipeline,
-   calculate market/model differences,
-   calculate implied volatility,
-   export normalized results.
-   Upstox option-chain payloads are fully normalized before batch pricing,
-   vendor-specific option type codes and identifiers do not appear in option-chain analytics output.

------------------------------------------------------------------------

# 56. Sprint 13 --- Volatility Smile

Implement visualization and analysis.

Display:

``` text
strike vs implied volatility
```

Optionally separate:

``` text
calls
puts
```

Do not interpret every model-market difference as arbitrage.

------------------------------------------------------------------------

# 57. Definition of Done --- V1

V1 is complete only when the following workflow succeeds:

``` text
Select or specify a real/listed-style contract
                 ↓
Load reproducible market data
                 ↓
Construct normalized market snapshot
                 ↓
Determine S, K, T, r, q, sigma
                 ↓
Create PricingRequest
                 ↓
Construct CRR tree
                 ↓
Price option
                 ↓
Calculate Greeks
                 ↓
Compare with market midpoint
                 ↓
Run diagnostics
                 ↓
Generate reproducible valuation result
```

Every major pricing input must be attributable to one of:

``` text
market observation
model assumption
transformation
interpolation
estimation
calibration
```

No important pricing parameter should appear without an identifiable
origin.

------------------------------------------------------------------------

# 58. Code Quality Requirements

All production code must:

-   use type hints,
-   use clear domain names,
-   have focused responsibilities,
-   avoid unnecessary inheritance,
-   avoid circular dependencies,
-   avoid duplicated pricing logic,
-   avoid hidden global configuration,
-   avoid hard-coded market values,
-   keep numerical code independent of UI,
-   include docstrings where behavior or mathematics is non-obvious.

Use dataclasses/frozen dataclasses where appropriate.

Prefer small cohesive modules.

------------------------------------------------------------------------

# 59. Numerical Requirements

Pay attention to:

-   floating-point tolerances,
-   near-zero maturity,
-   extreme strikes,
-   low volatility,
-   high volatility,
-   deep ITM/OTM options,
-   invalid probability values,
-   convergence oscillation,
-   root-finding bounds.

Never silently clamp mathematically invalid inputs simply to obtain a
price unless the behavior is explicitly documented and justified.

------------------------------------------------------------------------

# 60. Documentation Requirements

Maintain:

``` text
README.md
docs/
    architecture.md
    market_data.md
    crr_model.md
    volatility.md
    diagnostics.md
```

Documentation should explain:

-   business problem,
-   system architecture,
-   data flow,
-   CRR assumptions,
-   volatility choices,
-   rate/dividend conventions,
-   limitations,
-   reproduction instructions.

------------------------------------------------------------------------

# 61. README Final Demonstration

The README should eventually show one complete example:

``` text
Raw market data
      ↓
Normalized inputs
      ↓
CRR parameters
      ↓
Model price
      ↓
Market price
      ↓
Difference
      ↓
Greeks
      ↓
Diagnostics
```

Include a clear explanation of why model price need not equal market
price.

------------------------------------------------------------------------

# 62. Non-Goals

Do not turn this into:

-   a generic financial calculator,
-   an options tutorial application,
-   a trading bot,
-   a collection of disconnected pricing scripts,
-   a giant class supporting every derivative,
-   a UI-first project,
-   a project whose market-data code is mixed with numerical pricing
    code.

The central artifact is a **reproducible market-calibrated valuation
pipeline**.

------------------------------------------------------------------------

# 63. Codex Working Protocol

When asked to implement a sprint:

## Step 1

Inspect relevant existing files before editing.

## Step 2

Explain briefly:

``` text
Current state
Missing pieces
Files to change
Design decision
Tests to add
```

## Step 3

Implement only the requested sprint.

## Step 4

Run:

-   targeted tests,
-   relevant integration tests,
-   existing regression suite where appropriate.

## Step 5

Do not weaken existing tests merely to make new code pass.

## Step 6

Report:

``` text
Implemented
Files changed
Tests added
Test results
Known limitations
Next sprint
```

## Step 7

STOP.

Wait for explicit instruction before implementing the next sprint.

------------------------------------------------------------------------

# 64. First Instruction to Codex

Start with **Sprint 0 only**.

Inspect the current repository and produce:

``` text
docs/pyoptionpricer_gap_analysis.md
```

The analysis must map the current architecture against this
specification.

Specifically determine:

1.  what can be reused unchanged,
2.  what needs extension,
3.  what should be refactored,
4.  what is missing,
5.  which existing tests protect current behavior,
6.  whether the current `PricingRequest`, `MarketEnvironment`, engine
    registry, CRR engine, payoff hierarchy, exercise hierarchy,
    result/diagnostics objects, and service layer can support this
    project,
7.  the minimum architectural changes required before Sprint 1.

Do **not** implement Sprint 1 yet.

Do **not** create replacement abstractions when an existing abstraction
already satisfies the requirement.

Preserve backward compatibility unless there is a documented reason not
to.

The objective is to evolve the existing pricing system into the
market-calibrated tree pricer, not to rewrite it from scratch.
