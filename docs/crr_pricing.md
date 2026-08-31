# CRR pricing conventions

Sprint 5 prices plain-vanilla European and American calls and puts with a
recombining Cox-Ross-Rubinstein tree. A pricing request contains an immutable
`OptionContract`, a normalized `MarketSnapshot`, and `CRRModelParameters`.
Provider response objects and vendor-specific identifiers are not accepted by
the pricing layer.

Maturity is the Actual/365 Fixed difference between the contract expiry date
and snapshot valuation date. Rates and dividend yields are annual,
continuously compounded values selected at that maturity. Volatility is an
annualized decimal. For `N` steps the implementation uses:

```text
dt = T / N
u = exp(sigma * sqrt(dt))
d = 1 / u
p = (exp((r - q) * dt) - d) / (u - d)
discount = exp(-r * dt)
```

The request records resolved `S`, `K`, `T`, `r`, `q`, and `sigma` values along
with their source, source field, transformation method, and observation time
where one exists. Numeric volatility supplied directly to a snapshot is
identified explicitly as a model assumption.

European options use discounted risk-neutral continuation at every
pre-expiry node. American options use the greater of continuation and
intrinsic value at every node. The structured result contains the price,
currency, model configuration, resolved inputs, derived tree parameters, and
the number of nodes at which early exercise was selected, and tree-based
Delta, Gamma, and Theta.

## Greeks

Greeks are extracted from the first two levels of the same backward-induction
tree used for the option price, after applying the contract's exercise policy.
With node values ordered from down to up:

```text
Delta = (V_u - V_d) / (S_u - S_d)
Delta_up = (V_uu - V_ud) / (S_uu - S_ud)
Delta_down = (V_ud - V_dd) / (S_ud - S_dd)
Gamma = (Delta_up - Delta_down) / ((S_uu - S_dd) / 2)
Theta = (V_ud - V_0) / (2 * dt)
```

Delta is option-currency units per one currency unit of underlying movement.
Gamma is the change in Delta per one currency unit of underlying movement.
Theta is option-currency units per calendar year, with the sign representing
the value change as time advances. Consumers can divide Theta by their chosen
day-count basis when a per-day display is required.

At least two tree steps are required. Pricing fails explicitly rather than
returning a partial result if required levels are absent, any input is
non-finite, or the spot spacing is invalid for a finite-difference quotient.

The parameter calculation rejects non-positive maturity or volatility,
non-finite inputs, invalid step counts, and any risk-neutral probability
outside `[0, 1]`; it never clamps an invalid probability.

## Market comparison

Sprint 7 keeps market comparison outside the pricing engine. The
`compare_to_market` analytics function accepts a theoretical model price and a
canonical `OptionQuote`, regardless of its provider. It returns the model
price, bid, ask, midpoint, absolute difference, and percentage difference as a
structured `MarketComparison`.

The midpoint is `(bid + ask) / 2`. Both sides of the quote are required; the
last trade is not used as a fallback. The absolute difference is
`abs(model_price - market_mid)` in currency units, and percentage difference
is `absolute_difference / market_mid * 100`. A zero midpoint is rejected
because that percentage is undefined.

## Implied volatility

Sprint 9 calibrates annualized decimal volatility to the midpoint of any
canonical `OptionQuote`; provider-specific payloads are never accepted by the
solver. The initial volatility carried by the pricing request is replaced for
each trial while all other contract, market, model, and provenance inputs are
preserved.

The solver uses bisection over configurable positive lower and upper volatility
bounds. Convergence is measured in price space: the signed residual is
`CRR price - market midpoint`, and calibration succeeds when its absolute value
is no greater than the configured tolerance. A successful result includes the
implied volatility, midpoint, final structured pricing result, residual,
iteration count, and tolerance.

A two-sided quote with a positive midpoint is required. Invalid CRR states,
prices outside the configured bracket, and exhaustion of the iteration budget
raise explicit implied-volatility errors. Non-convergence errors retain the
iteration count and last pricing residual for diagnostics.
