# Market inputs

Pricing code consumes project-owned market models rather than provider payloads.
Maturity-aware interest-rate, dividend, and volatility inputs feed both the CRR
and BSM engines through normalized `PricingRequest` values.

## Rate conventions

- Maturity is expressed in years using **Actual/365 Fixed**.
- Zero rates use **annual continuous compounding**.
- Discount factors are calculated as `exp(-r(T) * T)`.
- `InterpolatedYieldCurve` linearly interpolates zero rates between adjacent
  maturity pillars. Before the first and after the last pillar, it uses the
  nearest pillar rate (flat endpoint extrapolation).
- A zero maturity is valid and has discount factor 1. Negative or non-finite
  maturities are invalid.

`FlatYieldCurve` supports the original V1 CSV format containing one rate per
currency and timestamp. CSV files may alternatively include a
`maturity_years` column with one row per curve pillar. Provider observations
remain attached to each curve so source provenance is retained.

## Dividend convention

V1 represents dividends as a non-negative annual continuous yield `q` using
the same Actual/365 Fixed time basis. Its discount factor is `exp(-q * T)`.
The `DividendYield` boundary keeps pricing independent of this initial flat
implementation and leaves room for discrete-dividend support in a later
version. In CRR cost-of-carry calculations, the intended input is `r(T) - q(T)`.

## Volatility conventions

`MarketImpliedVolatilitySurface` consumes canonical `OptionChain` entries, not
vendor response objects. Reliable points must be positive, no greater than the
configured maximum (5.0 decimal volatility by default), and have a future
expiry. Selection uses the exact strike/expiry when available, linear strike
interpolation within an expiry, and total-variance interpolation between
expiries. It does not extrapolate beyond observed strikes or expiries.

Surface output is a decimal annualized volatility with combined source,
dataset, observation-time, and retrieval-time provenance. The pricing request
marks it as a market-IV-surface selection. Historical estimators are optional
fallbacks and are never silently substituted for an unavailable market IV.

`HistoricalVolatility` and `EWMAVolatility` consume normalized close-price
observations or canonical historical bars; they contain no provider-specific
mapping logic. Both use close-to-close log returns `ln(S[t] / S[t-1])`. The
configurable `lookback` is a number of returns, so `lookback + 1` prices are
required. Only the most recent window is used after ordering inputs by their
timezone-aware timestamps.

Both estimators return an annualized decimal volatility. The default
annualization factor is 252 trading observations per year and the daily result
is multiplied by `sqrt(252)`. Historical volatility uses the sample standard
deviation (denominator `n - 1`) and therefore requires at least two returns.

EWMA initializes variance with the oldest squared return in the selected window
and recursively applies
`variance[t] = decay * variance[t-1] + (1 - decay) * return[t]^2`. Its default
decay is 0.94; callers can configure any finite value strictly between zero and
one. Insufficient histories and invalid model parameters fail with
`InvalidVolatilityInputError`.
