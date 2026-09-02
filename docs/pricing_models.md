# Pricing models and engine selection

Pricing requests select a model through a model-specific configuration object.
For example, `CRRModelParameters` identifies the canonical `PricingModel.CRR`
model and contains only CRR settings. The request exposes both `model` and a
`model_selection` view; existing callers that pass `CRRModelParameters` retain
the same request and result behavior.

`PRICING_ENGINE_ROUTES` in `pyoptionpricer.pricing.engine_router` is the single,
immutable composition point listing engines available in this repository. A new
engine becomes selectable only when its model-to-builder route is deliberately
added there; callers cannot register engines at runtime.

`build_available_pricing_engine(model)` accepts a `PricingModel` member or its
exact string value and constructs only that model's engine. The registry starts
without engine instances and caches an engine only after that model is selected.
It never eagerly constructs the complete catalogue, falls back, or delegates to
another model. Selecting a model with no available repository engine raises
`UnsupportedModelError`.

Each engine publishes immutable `EngineCapabilities` covering product families,
exercise styles, path dependency, and early exercise. The registry validates
the request against these capabilities before dispatch. Invalid combinations
raise `UnsupportedInstrumentModelCombinationError` with the selected model,
product family, exercise style, and reason as structured attributes.

`OptionContract` owns only the common static option terms. Its concrete
`VanillaOptionContract` and `DigitalOptionContract` subtypes provide their own
product identifier and terminal payoff; neither concrete product is modeled as
a subtype of the other.

CRR supports European, American, and Bermudan vanilla and cash-or-nothing
digital options, plus European vanilla single-barrier options. Bermudan contracts carry an explicit, normalized exercise
schedule, and contractual dates must align exactly with the selected CRR grid.
Black-Scholes-Merton (BSM) supports European vanilla and cash-or-nothing digital
calls and puts and is selected with
`BSMModelParameters`. BSM uses continuous compounding for the risk-free rate
and dividend yield and returns analytical Delta, Gamma, annual Theta, Vega, and
Rho. Vega and Rho are reported per unit (1.00) change, not per percentage point.

Digital options carry a configurable `cash_payout`. Both the call and put pay
zero when terminal spot is exactly equal to strike; payout requires strict
in-the-money settlement. Analytical digital Greeks are returned without
smoothing because their near-strike instability is economically meaningful.

`BarrierOptionContract` canonically represents up-and-out, down-and-out,
up-and-in, and down-and-in calls and puts. Phase 2 monitoring is discrete at
the valuation node and every CRR model time node; it is not a continuous-
monitoring approximation. A knock-out rebate is paid when the barrier is first
observed, while a knock-in rebate is paid at expiry only if the barrier was
never observed. Barrier state transitions live in a dedicated tree policy, so
the vanilla and digital lattice path is unchanged. `BarrierPricingDiagnostics`
records the barrier terms, monitoring and rebate conventions, tree steps, and
warnings when the barrier is off-grid or outside the reachable lattice range.
Zero-rebate knock-in and knock-out prices sum to the corresponding vanilla CRR
price under the same grid and market assumptions. BSM rejects barriers
explicitly because no analytical barrier strategy is included in this phase.

BSM product formulas are isolated behind `BSMProductPricer` strategies.
`BSM_PRODUCT_PRICERS` is the immutable composition point that maps each
supported `OptionProduct` to its strategy. Adding another analytical BSM
product therefore does not add product conditionals to `BSMPricingEngine`.
The engine, product strategies, and their shared numerical context are grouped
under the `pyoptionpricer.models.bsm` package. CRR parameters, lattice
construction, pricing, and convergence live under `pyoptionpricer.models.tree`.

`BSMModelParameters` exposes the maturity and volatility thresholds used to
select the deterministic discounted-payoff limit. This avoids division by a
vanishing standard deviation without silently clamping market inputs. At the
discounted at-the-money boundary the limit uses the symmetric 0.5 Delta
convention. `BSMPricingDiagnostics.calculation_mode` records whether the
analytical formula or deterministic limit was used, together with discount
factors and `d1`/`d2` when defined.

Monte Carlo supports European vanilla calls and puts under risk-neutral
geometric Brownian motion and is selected with `MonteCarloModelParameters`.
The configuration records the path count, time steps, integer seed, confidence
level, and whether antithetic variates are enabled. Antithetic runs require an
even path count and at least two complete pairs so uncertainty can be estimated
from independent pair averages.

Simulation responsibilities are separated under
`pyoptionpricer.models.monte_carlo`: `PythonRandomNumberGenerator` owns isolated
seeded random state, `GeometricBrownianMotion` applies exact finite-time GBM
transitions, `PathGenerator` streams complete paths, and
`TerminalPathPayoffEvaluator` adapts the existing terminal-payoff contract.
These components contain no market-provider behavior and are reusable by later
path-dependent products.

`MonteCarloPricingDiagnostics` returns the estimate, standard error, two-sided
normal confidence interval, actual path and time-step counts, seed, confidence
level, and variance-reduction method. Antithetic standard errors use pair
averages as the independent observations. Fixed-seed runs are deterministic on
the same supported Python runtime. The shared result also includes
common-random-number finite-difference Delta, Gamma, and annual Theta.
