# Convergence and diagnostics

Sprint 8 keeps diagnostics independent of presentation and vendor response
objects. Public diagnostic outcomes use stable `DiagnosticCode` and
`DiagnosticStatus` enums. `DiagnosticReport.overall_status` applies the
severity order `FAIL`, `WARN`, then `PASS`.

## CRR convergence

`CRRConvergenceRunner` reprices one immutable `PricingRequest` for every step
count in a `ConvergenceConfig`. Step counts must be unique, strictly
increasing integers of at least two. The default schedule is 10, 25, 50, 100,
250, 500, and 1000 steps.

The convergence implementation is colocated with the CRR model in
`pyoptionpricer.models.tree.convergence` and remains publicly exported from
`pyoptionpricer`.

Every outcome is retained as a `ConvergencePoint`. Successful points contain
the complete `PricingResult`; numerical or invalid-tree failures contain no
price and retain an error message. Any failed point makes the convergence
diagnostic `FAIL`, so an invalid tree cannot appear to be a valid convergence
run.

For an all-successful run, stability is measured as the maximum price minus
the minimum price over the configured final window. This captures alternating
odd/even CRR behavior rather than comparing only the final pair. A spread at
or below the absolute currency-unit tolerance is `PASS`; a larger spread is
`WARN`. The default tolerance is 0.01 over the last three prices.

## Pricing diagnostics

`diagnose_pricing_result` requires a result produced from the supplied request
and reports:

- contract validity;
- complete, internally consistent bid/ask quote data;
- quote freshness against a configurable positive duration (15 minutes by
  default);
- yield-curve and volatility availability;
- a finite risk-neutral probability in `[0, 1]`;
- the CRR factor condition `d <= exp((r-q)dt) <= u`; and
- theoretical option-price bounds.

A quote newer than the valuation time is `FAIL`. An incomplete two-sided quote
is `FAIL`, while a quote older than the freshness threshold is `WARN` because
it can still reproduce a theoretical valuation but should not be treated as
current market evidence.

For European options, the bounds use discounted spot and strike:

```text
call: max(S exp(-qT) - K exp(-rT), 0) <= C <= S exp(-qT)
put:  max(K exp(-rT) - S exp(-qT), 0) <= P <= K exp(-rT)
```

For American options, the lower bound is intrinsic value; the upper bound is
spot for a call and strike for a put.

Bermudan options use the European lower bound unless valuation day is an
eligible exercise date. Their upper bound is the corresponding American bound.

## Provider failures

`diagnose_provider_error` maps canonical provider exceptions to failed
authentication, data-availability, payload, capability, or general-provider
diagnostics. Upstox authentication, API availability, and payload exceptions
also inherit the corresponding canonical categories. This keeps downstream
handling vendor-neutral while retaining the Upstox-specific exception types
for adapter consumers. Upstox quote freshness is evaluated only after mapping
to the canonical `OptionQuote`.
