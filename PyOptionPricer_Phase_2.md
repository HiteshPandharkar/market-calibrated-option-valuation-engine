# PyOptionPricer — Phase 2: Multi-Model & Advanced Contract Pricing

## 1. Purpose

Phase 2 extends the existing Phase-1 PyOptionPricer architecture from a CRR-focused listed-option valuation engine into a multi-model option-pricing platform.

Phase 1 is assumed complete through Sprint 10 and already provides:

- provider-neutral market-data interfaces,
- CSV and Upstox market-data adapters,
- canonical contract and market-data models,
- normalized `MarketSnapshot`,
- yield-curve and continuous dividend-yield handling,
- historical, EWMA, and market-surface volatility selection,
- CRR pricing for European and American vanilla calls and puts,
- Delta, Gamma, and Theta,
- market-vs-model comparison,
- convergence and diagnostics,
- CRR implied-volatility calibration,
- reproducible end-to-end single-contract valuation,
- pricing-input provenance.

Phase 2 must build on these existing abstractions rather than replacing them.

The goal is to introduce:

- a generalized multi-model pricing architecture,
- Black-Scholes-Merton analytical pricing,
- model comparison and model-risk analytics,
- digital options,
- Bermudan exercise,
- barrier options,
- a reusable Monte Carlo pricing engine,
- Asian options,
- lookback options,
- one unified multi-model valuation workflow.

Phase 2 must preserve the Phase-1 principles of:

- provider independence,
- clean architecture,
- reproducibility,
- explicit assumptions,
- numerical validation,
- structured diagnostics,
- separation of pricing logic from market-data logic,
- separation of domain objects from presentation/UI code.

---

# 2. Phase 2 Scope

## 2.1 Pricing Models

Phase 2 must support:

```text
PricingModel
│
├── CRR
├── BLACK_SCHOLES_MERTON
└── MONTE_CARLO
```

The existing CRR implementation must remain supported.

---

## 2.2 Exercise Styles

Phase 2 must support:

```text
ExerciseStyle
│
├── EUROPEAN
├── AMERICAN
└── BERMUDAN
```

---

## 2.3 Payoff / Product Types

Phase 2 must support:

```text
Option Product
│
├── Vanilla
├── Digital
├── Barrier
├── Asian
└── Lookback
```

Initial implementations:

```text
Vanilla
├── Call
└── Put

Digital
├── Cash-or-Nothing Call
└── Cash-or-Nothing Put

Barrier
├── Up-and-Out
├── Down-and-Out
├── Up-and-In
└── Down-and-In

Asian
├── Arithmetic-Average Price Call
└── Arithmetic-Average Price Put

Lookback
├── Fixed-Strike Lookback Call
└── Fixed-Strike Lookback Put
```

---

# 3. Explicitly Out of Scope for Phase 2

Do not implement the following during Phase 2:

- FX options,
- commodity options,
- options on futures,
- chooser options,
- rainbow / multi-asset options,
- OTC lifecycle infrastructure,
- stochastic volatility,
- Heston,
- SABR,
- local volatility,
- finite-difference pricing,
- PDE solvers,
- stochastic interest rates,
- multi-factor rate models,
- portfolio optimization,
- trading strategies,
- order execution,
- market making,
- distributed computing,
- GPU simulation.

Do not introduce these abstractions prematurely merely because they may be useful later.

---

# 4. Architecture Direction

The target architecture is:

```text
Contract
   +
MarketSnapshot
   +
ModelSelection
   ↓
Capability Validation
   ↓
PricingEngineRegistry
   ↓
Selected Pricing Engine
   ↓
PricingResult
   ↓
Risk / Simulation Statistics
   ↓
Market Comparison
   ↓
Diagnostics
   ↓
Provenance
```

Model selection must not cause provider-specific logic to enter pricing code.

The market-data layer remains independent of all pricing engines.

---

# 5. Model Capability Architecture

Different pricing engines support different products and exercise styles.

The application must represent this explicitly.

Example conceptual capability model:

```python
EngineCapabilities(
    exercise_styles={...},
    payoff_types={...},
    supports_path_dependency=True | False,
    supports_early_exercise=True | False,
)
```

The exact implementation may differ if the existing repository already has a better abstraction.

Required behavior:

```text
Request
   ↓
Selected Model
   ↓
Capability Check
   ├── supported → price
   └── unsupported → explicit structured failure
```

Never silently switch pricing models.

Never silently simplify a product into another product type.

Example invalid combinations:

```text
BSM + American vanilla
BSM + Bermudan
BSM + arithmetic Asian
BSM + lookback
```

These must fail explicitly unless a specific supported analytical formula has deliberately been implemented.

---

# 6. Pricing Configuration

Avoid a giant universal model-parameter class containing unrelated fields.

Prefer model-specific configuration objects.

Conceptually:

```python
CRRModelParameters(...)
BSMModelParameters(...)
MonteCarloModelParameters(...)
```

Possible Monte Carlo fields:

```text
number_of_paths
time_steps
random_seed
antithetic_variates
confidence_level
```

Product-specific contract parameters must belong to product/domain objects rather than unrelated pricing-model configuration.

---

# 7. Pricing Result Evolution

Existing `PricingResult` behavior must remain compatible where practical.

Phase 2 may extend result metadata to support:

```text
model_name
model_parameters
price
currency
greeks
diagnostics
valuation_datetime
execution_metadata
numerical_statistics
```

For deterministic engines:

```text
numerical_statistics = None
```

For Monte Carlo:

```text
numerical_statistics
├── standard_error
├── confidence_interval
├── number_of_paths
├── random_seed
└── convergence_information
```

Do not overload `diagnostics` with normal Monte Carlo statistics.

---

# 8. Implementation Protocol

Every sprint must be implemented independently.

For every sprint, Codex must:

1. inspect the existing repository before editing;
2. identify reusable abstractions;
3. state the proposed changes;
4. implement only the requested sprint;
5. add/update unit tests;
6. add/update integration or regression tests where required;
7. run the relevant deterministic test suite;
8. fix failures introduced by that sprint;
9. summarize changed files;
10. document important mathematical or architectural decisions;
11. stop before starting the next sprint.

Do not automatically proceed to the following sprint.

Do not rewrite functioning Phase-1 architecture merely to match names in this document.

---

# Sprint P2.1 — Generalized Pricing Model Architecture

## Objective

Generalize the pricing layer so multiple pricing engines can coexist without breaking the existing CRR workflow.

## Implement

- define canonical pricing-model identifiers;
- generalize or extend the existing pricing-engine interface;
- generalize the engine registry/factory if required;
- create explicit engine capability metadata;
- create a capability-validation mechanism;
- create model-specific configuration types;
- preserve the existing CRR engine behind the generalized interface;
- preserve existing `PricingRequest` and `PricingResult` semantics where possible;
- add structured unsupported-model / unsupported-product errors.

Suggested concepts:

```text
PricingModel
PricingEngine
PricingEngineRegistry
EngineCapabilities
ModelCapabilityValidator
UnsupportedModelError
UnsupportedInstrumentModelCombinationError
```

Do not require these exact class names if equivalent abstractions already exist.

## Required Behavior

Conceptually:

```text
PricingRequest
     +
ModelSelection
     ↓
PricingEngineRegistry
     ↓
Capability Validation
     ↓
Pricing Engine
```

Example:

```text
European Vanilla + CRR
    → PASS

American Vanilla + CRR
    → PASS

European Vanilla + BSM
    → engine unavailable until P2.2

Asian + CRR
    → explicit unsupported combination
```

## Acceptance Criteria

- existing CRR tests continue to pass;
- Phase-1 end-to-end CRR valuation behavior remains unchanged;
- engine selection is configuration-driven;
- pricing services do not contain provider-specific conditions;
- model-specific configuration does not leak unrelated fields between engines;
- unsupported model/product combinations fail explicitly;
- no engine silently delegates to another engine;
- registry/factory tests exist;
- capability-validation tests exist;
- no circular dependency is introduced.

---

# Sprint P2.2 — Black-Scholes-Merton Analytical Engine

## Objective

Add a production-quality analytical Black-Scholes-Merton engine for European vanilla options.

## Supported Products

```text
European Vanilla Call
European Vanilla Put
```

## Implement

- BSM analytical pricing engine;
- continuous dividend-yield support;
- BSM-specific model parameter configuration;
- analytical:
  - Delta,
  - Gamma,
  - Theta,
  - Vega,
  - Rho where practical;
- structured diagnostics;
- input validation;
- engine registration;
- BSM documentation.

Use the same normalized market inputs used by CRR:

```text
spot
strike
time_to_expiry
risk_free_rate
dividend_yield
volatility
```

Do not read provider payloads inside the BSM engine.

## Numerical Requirements

Handle explicitly:

- zero or near-zero maturity;
- zero or invalid spot;
- zero or invalid strike;
- zero or near-zero volatility;
- extreme moneyness;
- invalid rates where unsupported by implementation assumptions.

Avoid hidden numerical clamping.

## Reference Tests

Create independently verified analytical test cases.

Also verify:

```text
CRR(N → sufficiently large)
        ≈
BSM
```

for European vanilla options under matching assumptions.

Tolerance must be documented.

## Acceptance Criteria

- European call prices match reference values within tolerance;
- European put prices match reference values within tolerance;
- put-call parity is tested;
- dividend yield is included correctly;
- Delta/Gamma/Theta tests exist;
- Vega/Rho tests exist if implemented;
- BSM consumes project-owned market/domain objects;
- BSM contains no vendor dependencies;
- BSM rejects unsupported exercise styles;
- CRR behavior remains unchanged.

---

# Sprint P2.3 — Cross-Model Valuation and Model-Risk Analytics

## Objective

Allow the same supported contract and market snapshot to be valued using multiple engines and compare the results.

## Implement

Create a model-comparison application/analytics service.

Conceptually:

```text
Contract
   +
MarketSnapshot
   ↓
Model Comparison Service
   ├── CRR
   └── BSM
        ↓
Comparison Result
```

Suggested result:

```python
ModelComparisonResult(
    market_mid=...,
    valuations={
        "CRR": ...,
        "BLACK_SCHOLES_MERTON": ...,
    },
    pairwise_price_differences=...,
    greek_differences=...,
    diagnostics=...,
)
```

## Required Outputs

For a European vanilla contract:

```text
Market Bid
Market Ask
Market Mid

CRR Price
BSM Price

Market Mid - CRR
Market Mid - BSM
CRR - BSM
```

Where available, compare:

```text
Delta
Gamma
Theta
```

## Rules

Do not interpret model disagreement automatically as:

```text
arbitrage
pricing error
market inefficiency
```

The result must identify:

- model name,
- assumptions,
- volatility input,
- rate input,
- dividend input,
- numerical parameters,
- provenance.

## Acceptance Criteria

- same normalized `MarketSnapshot` can feed CRR and BSM;
- model comparison is independent of UI;
- comparison is deterministic;
- model-specific diagnostics remain accessible;
- the service does not duplicate pricing formulas;
- unsupported model combinations are handled explicitly;
- comparison tests exist.

---

# Sprint P2.4 — Digital Options

## Objective

Introduce the first non-vanilla payoff without coupling payoff logic to a specific pricing engine.

## Initial Scope

Implement:

```text
Cash-or-Nothing Digital Call
Cash-or-Nothing Digital Put
```

Required contract parameter:

```text
cash_payout
```

## Domain Design

Create a project-owned digital payoff abstraction.

Conceptually:

```python
CashOrNothingPayoff(
    option_type=CALL | PUT,
    strike=...,
    payout=...,
)
```

Terminal payoff:

```text
Call:
payout if S_T > K
else 0

Put:
payout if S_T < K
else 0
```

Boundary convention at:

```text
S_T == K
```

must be explicitly documented.

## Pricing Support

Implement:

- CRR digital pricing;
- BSM analytical digital pricing where assumptions align.

## Numerical Concerns

Digital payoffs are discontinuous.

Tests must investigate:

- CRR convergence behavior;
- strike-near-terminal-node effects;
- sensitivity instability;
- finite precision around strike.

Do not hide unstable Greeks.

## Acceptance Criteria

- digital call payoff tests pass;
- digital put payoff tests pass;
- payout amount is configurable;
- CRR pricing works;
- BSM analytical reference works where supported;
- CRR and BSM convergence comparison exists;
- vanilla payoff implementation remains unchanged;
- pricing engines use generic payoff/product abstractions where appropriate.

---

# Sprint P2.5 — Bermudan Exercise

## Objective

Generalize exercise handling to support options exercisable only on predefined dates.

## Implement

Add Bermudan exercise policy.

Conceptually:

```python
BermudanExercise(
    exercise_dates=(...)
)
```

Requirements:

- exercise schedule must not be empty;
- exercise dates must be ordered or normalized deterministically;
- exercise dates must not occur after expiry;
- expiry handling must be explicit;
- duplicate dates must be handled explicitly;
- valuation-date edge cases must be validated.

## CRR Integration

At each tree time step:

```text
Is this an eligible Bermudan exercise date?
        │
        ├── NO → continuation value
        │
        └── YES
             ↓
      max(
          continuation_value,
          intrinsic_value
      )
```

## Time Mapping

Tree nodes occur on discrete model times.

Define and document how contractual exercise dates are mapped to CRR time steps.

Do not use hidden nearest-date behavior.

If exact alignment is required, reject incompatible grids.

If deterministic mapping is allowed, document the convention and tolerance.

## Acceptance Criteria

- European exercise tests remain unchanged;
- American exercise tests remain unchanged;
- Bermudan schedule validation exists;
- early exercise occurs only at eligible dates;
- Bermudan price lies between appropriate European/American benchmark values where assumptions permit;
- exercise-policy logic remains separate from generic tree mechanics;
- unsupported engines reject Bermudan contracts explicitly.

---

# Sprint P2.6 — Barrier Options

## Objective

Add single-barrier options while preserving separation between contract state, payoff logic, and pricing mechanics.

## Initial Scope

Implement:

```text
Up-and-Out
Down-and-Out
Up-and-In
Down-and-In
```

Initial underlying payoff:

```text
European Vanilla Call
European Vanilla Put
```

## Contract Parameters

Represent explicitly:

```text
barrier_level
barrier_direction
knock_type
rebate
monitoring_convention
```

Suggested enums:

```text
BarrierDirection
├── UP
└── DOWN

BarrierKnockType
├── IN
└── OUT
```

## Monitoring

Phase 2 must clearly specify supported monitoring.

Initial recommended scope:

```text
discrete monitoring on model time nodes
```

Do not claim continuous-monitoring equivalence.

## CRR Implementation

Track barrier state during tree valuation.

Do not insert large barrier-specific conditional blocks directly into generic lattice construction if a cleaner state/policy abstraction is possible.

## Required Diagnostics

Include:

```text
barrier level
barrier type
monitoring convention
rebate
tree steps
barrier/grid alignment warnings
```

## Tests

Include:

- barrier never reached;
- barrier reached immediately;
- deep barrier;
- barrier near spot;
- rebate behavior;
- knock-in/knock-out consistency where theoretical relationships apply.

## Acceptance Criteria

- four barrier directions/types are represented canonically;
- CRR pricing works for supported contracts;
- monitoring convention is explicit;
- barrier logic does not modify vanilla contracts;
- unsupported engines fail explicitly;
- result identifies barrier assumptions;
- relevant parity/reference tests exist.

---

# Sprint P2.7 — Monte Carlo Engine Foundation

## Objective

Create a reusable Monte Carlo pricing framework before implementing path-dependent products.

Do not build Monte Carlo directly inside an Asian or lookback option class.

## Architecture

Target decomposition:

```text
RandomNumberGenerator
        ↓
StochasticProcess
        ↓
PathGenerator
        ↓
Generated Paths
        ↓
Path Payoff Evaluator
        ↓
MonteCarloPricingEngine
        ↓
Estimate + Statistics
```

The exact class structure may differ based on existing architecture.

## Initial Stochastic Process

Implement:

```text
Geometric Brownian Motion
```

under the risk-neutral measure.

Conceptually:

```text
dS = (r - q) S dt + sigma S dW
```

Use a mathematically appropriate exact GBM transition where practical.

## Monte Carlo Configuration

Support:

```text
number_of_paths
time_steps
random_seed
antithetic_variates
confidence_level
```

## Reproducibility

Given identical:

```text
contract
market snapshot
model configuration
seed
```

the Monte Carlo result must be reproducible.

## Required Output Statistics

Return:

```text
estimated_price
standard_error
confidence_interval
number_of_paths
time_steps
seed
variance_reduction_method
execution_time where existing architecture supports it
```

## First Validation Product

Price European vanilla options first.

Compare:

```text
Monte Carlo
    vs
BSM
```

The purpose is to validate the simulation framework before using path-dependent payoffs.

## Variance Reduction

Implement at least:

```text
antithetic variates
```

Do not add multiple advanced variance-reduction techniques in this sprint.

## Acceptance Criteria

- deterministic seeded runs reproduce exactly or within documented deterministic platform expectations;
- GBM path-generation tests exist;
- terminal distribution sanity tests exist;
- Monte Carlo European vanilla price agrees with BSM within statistically justified tolerance;
- standard error is returned;
- confidence interval is returned;
- increasing path count demonstrates expected convergence behavior in tests/benchmarks without brittle exact assertions;
- simulation code contains no market-provider logic;
- no Asian/lookback-specific behavior exists in the core simulation engine.

---

# Sprint P2.8 — Asian Options

## Objective

Use the reusable Monte Carlo engine to price arithmetic-average price Asian options.

## Initial Scope

Implement:

```text
Arithmetic Average Price Call
Arithmetic Average Price Put
```

Payoff:

```text
Call:
max(A - K, 0)

Put:
max(K - A, 0)
```

where:

```text
A = arithmetic mean of monitored underlying prices
```

## Contract Requirements

Represent observation schedule explicitly.

Do not assume every Monte Carlo step is necessarily an observation date unless that is the explicitly configured convention.

Conceptually:

```python
AsianOption(
    ...,
    averaging_method=ARITHMETIC,
    observation_schedule=(...),
)
```

## Pricing

Use:

```text
MonteCarloPricingEngine
```

Do not create an independent Asian simulation loop.

## Required Diagnostics

Report:

```text
number_of_paths
time_steps
observation_count
averaging_method
random_seed
standard_error
confidence_interval
```

## Tests

Include:

- payoff unit tests using deterministic paths;
- one observation;
- multiple observations;
- call/put payoff behavior;
- reproducible seeded pricing;
- convergence with increasing path count;
- malformed observation schedule.

## Acceptance Criteria

- arithmetic-average call works;
- arithmetic-average put works;
- observation schedule is explicit;
- payoff logic is independently testable;
- generic Monte Carlo engine is reused;
- no duplicated GBM simulation implementation exists;
- numerical statistics are returned;
- unsupported engines reject Asian options.

---

# Sprint P2.9 — Lookback Options

## Objective

Introduce a second path-dependent product using the same Monte Carlo infrastructure.

## Initial Scope

Implement fixed-strike lookback options:

```text
Fixed-Strike Lookback Call
Fixed-Strike Lookback Put
```

Conceptual payoffs:

```text
Call:
max(S_max - K, 0)

Put:
max(K - S_min, 0)
```

where `S_max` and `S_min` are evaluated over the supported monitoring schedule.

## Contract Requirements

Represent monitoring schedule/convention explicitly.

Do not silently imply continuous monitoring.

## Pricing

Use the existing Monte Carlo engine from P2.7.

The payoff evaluator may consume the generated path and extract:

```text
running maximum
running minimum
```

## Tests

Include deterministic path tests:

```text
monotonically increasing path
monotonically decreasing path
flat path
path crossing strike
```

Also test:

- reproducibility;
- standard-error reporting;
- increased path-count convergence;
- malformed monitoring schedules.

## Acceptance Criteria

- fixed-strike lookback call works;
- fixed-strike lookback put works;
- generic Monte Carlo infrastructure is reused;
- no duplicated stochastic-process code exists;
- monitoring convention is explicit;
- path-extrema payoff logic is independently testable;
- unsupported engines reject lookback options.

---

# Sprint P2.10 — Unified Multi-Model Valuation Workflow

## Objective

Complete Phase 2 by exposing one consistent application workflow across all supported products and models.

## Target Flow

```text
Contract Selection / Construction
            ↓
Normalized MarketSnapshot
            ↓
Pricing Model Selection
            ↓
Model-Specific Configuration
            ↓
Capability Validation
            ↓
PricingEngineRegistry
            ↓
Selected Pricing Engine
            ↓
PricingResult
            ↓
Greeks / Numerical Statistics
            ↓
Market Comparison where meaningful
            ↓
Diagnostics
            ↓
Provenance
```

## Supported Matrix

The application must maintain an explicit tested compatibility matrix.

Initial target:

| Product | Exercise | CRR | BSM | Monte Carlo |
|---|---|---:|---:|---:|
| Vanilla Call/Put | European | Yes | Yes | Yes |
| Vanilla Call/Put | American | Yes | No | No* |
| Vanilla Call/Put | Bermudan | Yes | No | No* |
| Digital Cash-or-Nothing | European | Yes | Yes | Optional |
| Barrier | European | Yes | No | Optional |
| Asian Arithmetic Average | European | No | No | Yes |
| Lookback Fixed Strike | European | No | No | Yes |

`No*` means do not implement regression-based Monte Carlo early-exercise methods in Phase 2.

## Application Service Requirements

The public workflow must not become:

```python
if product == "asian":
    ...
elif product == "barrier":
    ...
elif model == "crr":
    ...
```

Use domain polymorphism, registries, strategy objects, capability metadata, dispatch maps, or other focused abstractions appropriate to the existing architecture.

Avoid a giant central service.

## Market Comparison

Market comparison is valid only when a usable observed quote exists for the selected contract.

Do not fabricate market prices for exotic contracts.

If no quote exists:

```text
market_comparison = unavailable
```

with a structured reason.

## Provenance

Every major input must remain attributable to:

```text
market observation
model assumption
contract specification
transformation
interpolation
estimation
calibration
simulation configuration
```

Monte Carlo seed and numerical settings must be reproducible metadata.

## Diagnostics

Unified diagnostics should distinguish:

```text
contract diagnostics
market-data diagnostics
model diagnostics
capability diagnostics
numerical diagnostics
simulation diagnostics
```

Do not reduce them to unstructured log strings.

## Acceptance Criteria

A single application-level interface can price every supported Phase-2 combination without provider-specific or UI-specific logic.

Required tests:

- CRR European vanilla end-to-end;
- CRR American vanilla end-to-end;
- CRR Bermudan vanilla end-to-end;
- BSM European vanilla end-to-end;
- CRR digital end-to-end;
- BSM digital end-to-end;
- CRR barrier end-to-end;
- Monte Carlo European vanilla end-to-end;
- Monte Carlo Asian end-to-end;
- Monte Carlo lookback end-to-end;
- unsupported product/model combination tests;
- deterministic provider-neutral market snapshot tests;
- Monte Carlo reproducibility tests;
- Phase-1 regression tests.

---

# 9. Phase 2 Definition of Done

Phase 2 is complete only when the following generalized workflow works:

```text
Select Contract
      ↓
Load / Construct MarketSnapshot
      ↓
Select Pricing Model
      ↓
Validate Model Capability
      ↓
Resolve Model Parameters
      ↓
Run Pricing Engine
      ↓
Produce PricingResult
      ↓
Calculate / Attach Risk Measures
      ↓
Attach Numerical Statistics
      ↓
Compare With Market Where Available
      ↓
Run Diagnostics
      ↓
Preserve Provenance
      ↓
Generate Reproducible Result
```

The system must support at least:

```text
European Vanilla + CRR
European Vanilla + BSM
European Vanilla + Monte Carlo

American Vanilla + CRR
Bermudan Vanilla + CRR

European Digital + CRR
European Digital + BSM

European Barrier + CRR

European Arithmetic Asian + Monte Carlo
European Fixed-Strike Lookback + Monte Carlo
```

---

# 10. Phase 2 Code Quality Requirements

All production code must:

- preserve Phase-1 provider neutrality;
- use project-owned domain terminology;
- use type hints;
- keep pricing engines independently testable;
- separate product/payoff logic from market-data retrieval;
- separate stochastic-process logic from payoff evaluation;
- avoid duplicate simulation implementations;
- avoid model-selection conditional explosions;
- avoid hidden model fallback;
- avoid hidden numerical clamping;
- avoid mutable global RNG state;
- avoid hard-coded seeds in production defaults unless explicitly documented;
- preserve input provenance;
- preserve deterministic offline tests;
- document non-obvious mathematical conventions;
- expose unsupported configurations clearly.

---

# 11. Numerical Requirements

Phase 2 must explicitly address:

```text
near-zero maturity
near-zero volatility
deep ITM / OTM contracts
digital payoff discontinuity
barrier/grid alignment
Bermudan date/grid alignment
Monte Carlo standard error
confidence intervals
simulation convergence
random-seed reproducibility
path observation schedules
floating-point tolerances
CRR convergence to BSM
```

Do not use exact floating-point equality unless mathematically justified.

Monte Carlo tests must use statistically appropriate tolerances.

---

# 12. Documentation Requirements

Add or update documentation for:

```text
docs/
├── architecture.md
├── pricing_models.md
├── bsm_model.md
├── model_comparison.md
├── digital_options.md
├── bermudan_options.md
├── barrier_options.md
├── monte_carlo.md
├── asian_options.md
├── lookback_options.md
└── model_capabilities.md
```

Adapt this list to the repository's existing documentation structure rather than creating duplicate documentation.

Document:

- supported model/product matrix;
- assumptions;
- formulas;
- numerical methods;
- exercise conventions;
- monitoring conventions;
- observation schedules;
- Monte Carlo reproducibility;
- confidence intervals;
- known limitations;
- unsupported combinations.

---

# 13. Phase 2 Non-Goals

Do not turn Phase 2 into:

- a generic derivatives platform supporting every asset class;
- a stochastic-volatility research project;
- a PDE framework;
- an OTC lifecycle system;
- a portfolio risk engine;
- a trading system;
- a collection of disconnected pricing scripts;
- separate application pipelines for every option type;
- separate market-data implementations for every pricing model.

The central artifact after Phase 2 must be:

> A provider-neutral, reproducible, multi-model option valuation engine capable of selecting an appropriate pricing method for vanilla, early-exercise, discontinuous-payoff, barrier, and path-dependent option contracts while preserving model assumptions, diagnostics, numerical uncertainty, and input provenance.

---

# 14. Codex Stop Rule

When implementing a requested sprint:

```text
Inspect
   ↓
Plan
   ↓
Implement requested sprint only
   ↓
Test
   ↓
Fix sprint-introduced failures
   ↓
Document
   ↓
Summarize
   ↓
STOP
```

Do not begin the next sprint unless explicitly instructed.
