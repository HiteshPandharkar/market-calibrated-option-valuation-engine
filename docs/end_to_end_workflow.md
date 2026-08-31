# Single-contract valuation workflow

Sprint 10 provides one application service for the complete provider-neutral
workflow. `SingleContractValuationService.value()` resolves the canonical
contract, retrieves a normalized option chain, builds/interpolates the market
implied-volatility surface, selects the contract IV, builds a normalized market
snapshot, creates a `PricingRequest`, runs the CRR engine and Greeks, compares
the result with bid/ask/mid, and runs structured diagnostics. Its result contains each
intermediate object so callers can audit or present the valuation without
repeating business logic.

## Provider selection

`MarketDataProviderConfiguration` and `MarketDataProviderFactory` select one
provider using the names `csv` or `upstox`. The factory is a composition-root
registry: applications can inject another registered builder without adding
vendor conditionals to pricing or workflow code.

Provider fallback is deliberately absent. The Upstox V1 adapter supplies
instrument references, quotes, and price history, but not risk-free curves or
dividend forecasts. An Upstox request must therefore pass those inputs
explicitly as project-owned `YieldCurve` and `DividendYield` objects. Their
`MarketObservation` metadata records the independent source or the fact that
the value is a model assumption. The workflow never retrieves them silently
from CSV or another vendor.

For providers with `OptionChainProvider` capability, provider volatility means
market IV. Vendor chain rows are normalized to `OptionChain`, unreliable IVs
are removed, and `MarketImpliedVolatilitySurface` selects an exact point or
interpolates linearly by strike. Between expiries it interpolates total
variance. The surface never extrapolates. A history-derived historical or EWMA
volatility is available only when `fallback_source` (CLI
`--volatility-fallback`) is explicitly configured. Fallback use is exposed on
the valuation result and in CLI output. Providers without option-chain support,
including the sample CSV provider, retain their normalized scalar volatility
input for backward compatibility.

Underlying and option observations must be no more than 15 minutes old and
their timestamps must be within two minutes of each other by default. The
workflow fails explicitly instead of combining stale or unsynchronized market
states. A live quote may arrive up to 30 seconds after the workflow's requested
start time; in that case the effective snapshot time advances to the latest
quote. All three limits are configurable on `SingleContractValuationRequest`.

Every completed valuation contains two volatility views: the market-surface IV
used to derive CRR up/down factors and risk-neutral probability, and the CRR IV
independently calibrated to the contemporaneous option midpoint as a diagnostic.
The CLI reports the surface point count, selected IV, fallback status, calibrated
IV, price residual, and iteration count.

## Reproducible sample command

After installing the package with `python -m pip install -e .`, the committed
sample files reproduce a complete valuation with:

```powershell
price-option --provider csv `
  --data-directory tests/fixtures/market_data `
  --underlying-id ACME `
  --contract-id ACME-20261231-1400-C `
  --valuation-time 2026-08-28T15:30:00+00:00 `
  --strike 1400 `
  --expiry 2026-12-31 `
  --type CALL `
  --exchange SAMPLE_EXCHANGE `
  --steps 200
```

The command is a thin JSON presentation over the application service. With a
source checkout that is not installed, the equivalent PowerShell invocation is
`$env:PYTHONPATH='src'; python -m pyoptionpricer ...`.

The deterministic Upstox end-to-end test uses stored raw response fixtures and
the real Upstox adapter. Network smoke tests remain isolated under the
`live_upstox` marker and skip unless the opt-in environment variables and
network access are available.

The opt-in live workflow accepts `UPSTOX_TEST_INSTRUMENT_KEY` and
`UPSTOX_TEST_OPTION_INSTRUMENT_KEY` as Upstox vendor instrument keys, retrieves
the exact instrument references, option chain with vendor IV, and underlying quote,
and requires explicit `UPSTOX_TEST_RISK_FREE_RATE` and
`UPSTOX_TEST_DIVIDEND_YIELD` assumptions. It skips when the selected contract is
expired or the market observations are not contemporaneous. Historical data is
retrieved only when a configured fallback is needed.
