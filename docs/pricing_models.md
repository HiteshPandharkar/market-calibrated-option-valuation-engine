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

Sprint P2.1 registers CRR for European and American vanilla options. The
canonical identifiers for Black-Scholes-Merton and Monte Carlo are reserved for
their later implementations; attempting to select either before its engine is
implemented fails explicitly.
