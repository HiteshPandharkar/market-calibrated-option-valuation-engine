# PyOptionPricer

PyOptionPricer is a provider-neutral Python engine for valuing European,
American, and Bermudan options with the Cox-Ross-Rubinstein (CRR) binomial
model and European
vanilla and cash-or-nothing digital options with analytical Black-Scholes-Merton
(BSM). It combines normalized market data
with auditable input provenance, tree-based Greeks, market comparison,
implied-volatility calibration, convergence analysis, and structured
diagnostics.

The project includes two market-data adapters:

- a deterministic CSV provider for reproducible local runs and tests; and
- an Upstox adapter for normalized instrument, quote, option-chain, and price
  history data.

Pricing and workflow code depend only on project-owned interfaces, so vendor
details remain isolated at the application boundary.

## Requirements and installation

- Python 3.11 or newer
- `pip`

Create and activate a virtual environment, then install the package and test
dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
```

## Quick start

The committed CSV fixtures reproduce a complete single-contract valuation:

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

The command emits JSON containing the theoretical price, Delta/Gamma/Theta,
bid/ask/mid comparison, calibrated implied volatility, diagnostic status, and
the provenance of every resolved pricing input. Run `price-option --help` for
all options.

From an uninstalled source checkout, prefix the equivalent module command with
`$env:PYTHONPATH='src'` and use `python -m pyoptionpricer` in place of
`price-option`.

## Capabilities

- CRR valuation for European, American, and Bermudan vanilla and
  cash-or-nothing digital calls and puts
- analytical BSM valuation and Delta/Gamma/Theta/Vega/Rho for European vanilla and cash-or-nothing digital calls and puts
- configurable digital cash payouts with a strict, zero-payoff strike boundary
- maturity-aware yield curves and continuous dividend yields
- historical, EWMA, and market-surface volatility selection
- Delta, Gamma, and annualized Theta calculated from the tree
- bid/ask/mid comparison against canonical option quotes
- CRR implied-volatility calibration to the market midpoint
- convergence runs and machine-readable pricing diagnostics
- end-to-end single-contract workflows with complete input provenance
- canonical model selection with explicit engine capability validation
- deterministic, provider-neutral CSV and Upstox test paths

## Package layout

Model implementations are grouped by model rather than mixed into the shared
pricing orchestration package:

```text
pyoptionpricer/
├── models/
│   ├── bsm/
│   │   ├── engine.py
│   │   └── products.py
│   └── tree/
│       ├── crr.py
│       ├── parameters.py
│       ├── pricing_engine.py
│       └── convergence.py
└── pricing/
    ├── engine_registry.py
    ├── engine_router.py
    ├── requests.py
    └── results.py
```

`OptionContract` defines common option terms. `VanillaOptionContract` and
`DigitalOptionContract` supply their own product identifiers and terminal
payoffs. Stable public imports remain available from `pyoptionpricer`.

Market implied volatility is preferred when a provider supplies a reliable
option chain. Historical or EWMA volatility is used only when an explicit
fallback is configured. The Upstox adapter does not supply risk-free curves or
dividend forecasts, so live Upstox valuations must provide those assumptions
explicitly.

## Tests

Run the deterministic suite, which uses no network access:

```powershell
python -m pytest -m "not live_upstox" -q
```

The live Upstox tests are opt-in. Copy the variable names from `.env.example`
into the process environment or a local, git-ignored `.env`, then provide:

- `UPSTOX_ACCESS_TOKEN`
- `UPSTOX_TEST_INSTRUMENT_KEY`
- `UPSTOX_TEST_OPTION_INSTRUMENT_KEY`
- `UPSTOX_TEST_RISK_FREE_RATE`
- `UPSTOX_TEST_DIVIDEND_YIELD`
- `UPSTOX_RUN_LIVE_TESTS=1`

Run the live smoke tests with:

```powershell
python -m pytest -m live_upstox -q
```

Use a short-lived Upstox token and never commit credentials. Exported process
variables take precedence over `.env`; credential values are not printed or
copied into global environment state.

## Documentation

- [End-to-end workflow](docs/end_to_end_workflow.md)
- [CRR pricing, Greeks, market comparison, and implied volatility](docs/crr_pricing.md)
- [Pricing models, registry selection, and capabilities](docs/pricing_models.md)
- [Market-data and volatility conventions](docs/market_data.md)
- [Convergence and diagnostics](docs/diagnostics.md)
- [Upstox mappings and capability limits](docs/vendor_mapping_upstox.md)
