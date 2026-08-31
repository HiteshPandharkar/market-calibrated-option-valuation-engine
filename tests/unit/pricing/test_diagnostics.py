from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

import pytest

from pyoptionpricer import (
    AssetClass,
    CRRConvergenceRunner,
    CRRModelParameters,
    CRRPricingEngine,
    ConvergenceConfig,
    Currency,
    DiagnosticCode,
    DiagnosticStatus,
    ExerciseStyle,
    OptionContract,
    OptionType,
    PricingRequest,
    diagnose_pricing_result,
    diagnose_provider_error,
)
from pyoptionpricer.market import (
    ContinuousDividendYield,
    FlatYieldCurve,
    MarketDataUnavailableError,
    MarketObservation,
    MarketSnapshot,
    OptionQuote,
    UnsupportedMarketDataCapabilityError,
)
from pyoptionpricer.market.data.providers.upstox import (
    UpstoxAPIError,
    UpstoxAuthenticationError,
    UpstoxPayloadError,
)


VALUATION = datetime(2026, 8, 30, 12, tzinfo=UTC)


def make_request(
    *,
    quote: OptionQuote | None = None,
    rate: float = 0.05,
    volatility: float = 0.20,
    steps: int = 200,
) -> PricingRequest:
    contract = OptionContract(
        "ACME",
        100.0,
        date(2027, 8, 30),
        OptionType.CALL,
        ExerciseStyle.EUROPEAN,
        AssetClass.EQUITY,
        currency=Currency.USD,
    )
    timestamp = VALUATION - timedelta(minutes=1)
    snapshot = MarketSnapshot(
        valuation_datetime=VALUATION,
        spot=MarketObservation(100.0, timestamp, "TEST", "last_price"),
        option_quote=quote or OptionQuote(9.0, 10.0, 9.5, timestamp),
        yield_curve=FlatYieldCurve(rate),
        dividend_data=ContinuousDividendYield(0.0),
        volatility_input=volatility,
    )
    return PricingRequest(contract, snapshot, CRRModelParameters(steps))


def test_pricing_diagnostics_pass_for_valid_fresh_valuation() -> None:
    request = make_request()
    result = CRRPricingEngine().price(request)

    report = diagnose_pricing_result(request, result)

    assert report.overall_status is DiagnosticStatus.PASS
    assert report.get(DiagnosticCode.RISK_NEUTRAL_PROBABILITY).status is DiagnosticStatus.PASS
    assert report.get(DiagnosticCode.NO_ARBITRAGE).status is DiagnosticStatus.PASS


def test_data_quality_diagnostics_report_incomplete_and_stale_quote() -> None:
    quote = OptionQuote(
        bid=None,
        ask=None,
        last=9.5,
        timestamp=VALUATION - timedelta(hours=1),
    )
    request = make_request(quote=quote)
    result = CRRPricingEngine().price(request)

    report = diagnose_pricing_result(
        request, result, quote_stale_after=timedelta(minutes=5)
    )

    assert report.overall_status is DiagnosticStatus.FAIL
    assert report.get(DiagnosticCode.MARKET_QUOTE_VALIDITY).status is DiagnosticStatus.FAIL
    assert report.get(DiagnosticCode.QUOTE_FRESHNESS).status is DiagnosticStatus.WARN


def test_no_arbitrage_diagnostic_rejects_impossible_stored_price() -> None:
    request = make_request()
    result = CRRPricingEngine().price(request)

    report = diagnose_pricing_result(request, replace(result, price=101.0))

    assert report.get(DiagnosticCode.NO_ARBITRAGE).status is DiagnosticStatus.FAIL
    assert report.overall_status is DiagnosticStatus.FAIL


def test_convergence_runner_stores_each_resolution_and_passes_stable_tail() -> None:
    config = ConvergenceConfig((100, 200, 400), tolerance=0.02, stability_window=2)

    result = CRRConvergenceRunner().run(make_request(), config)

    assert [point.steps for point in result.points] == [100, 200, 400]
    assert all(point.pricing_result is not None for point in result.points)
    assert result.converged
    assert result.diagnostic.status is DiagnosticStatus.PASS


def test_convergence_runner_warns_when_tail_is_not_within_tolerance() -> None:
    config = ConvergenceConfig((10, 20, 40), tolerance=1e-12, stability_window=3)

    result = CRRConvergenceRunner().run(make_request(), config)

    assert not result.converged
    assert result.diagnostic.status is DiagnosticStatus.WARN


def test_invalid_tree_states_are_stored_as_failed_convergence_points() -> None:
    config = ConvergenceConfig((2, 4, 8), tolerance=0.01, stability_window=2)

    result = CRRConvergenceRunner().run(
        make_request(rate=1.0, volatility=0.01), config
    )

    assert result.diagnostic.status is DiagnosticStatus.FAIL
    assert all(point.price is None and point.error for point in result.points)


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (UpstoxAuthenticationError("authentication failed"), DiagnosticCode.PROVIDER_AUTHENTICATION),
        (MarketDataUnavailableError("quote unavailable"), DiagnosticCode.PROVIDER_DATA_AVAILABILITY),
        (UpstoxAPIError("request unavailable"), DiagnosticCode.PROVIDER_DATA_AVAILABILITY),
        (UpstoxPayloadError("malformed payload"), DiagnosticCode.PROVIDER_PAYLOAD),
        (
            UnsupportedMarketDataCapabilityError("unsupported"),
            DiagnosticCode.PROVIDER_CAPABILITY,
        ),
    ],
)
def test_provider_failures_have_structured_diagnostics(
    error: Exception, code: DiagnosticCode
) -> None:
    diagnostic = diagnose_provider_error(error)  # type: ignore[arg-type]

    assert diagnostic.code is code
    assert diagnostic.status is DiagnosticStatus.FAIL
