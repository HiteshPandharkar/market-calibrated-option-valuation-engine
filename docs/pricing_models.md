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

CRR supports European and American vanilla options. Black-Scholes-Merton (BSM)
supports European vanilla calls and puts and is selected with
`BSMModelParameters`. BSM uses continuous compounding for the risk-free rate
and dividend yield and returns analytical Delta, Gamma, annual Theta, Vega, and
Rho. Vega and Rho are reported per unit (1.00) change, not per percentage point.

`BSMModelParameters` exposes the maturity and volatility thresholds used to
select the deterministic discounted-payoff limit. This avoids division by a
vanishing standard deviation without silently clamping market inputs. At the
discounted at-the-money boundary the limit uses the symmetric 0.5 Delta
convention. `BSMPricingDiagnostics.calculation_mode` records whether the
analytical formula or deterministic limit was used, together with discount
factors and `d1`/`d2` when defined.

Monte Carlo remains reserved for its later implementation; selecting it fails
explicitly.
