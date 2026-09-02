"""Machine-readable diagnostics for pricing and provider failures."""

from dataclasses import dataclass
from datetime import timedelta
from enum import Enum
from math import exp, isfinite

from pyoptionpricer.domain import (
    BarrierOptionContract,
    CashOrNothingPayoff,
    ExerciseStyle,
    OptionType,
)
from pyoptionpricer.market.exceptions import (
    MalformedMarketDataError,
    MarketDataAuthenticationError,
    MarketDataProviderError,
    MarketDataUnavailableError,
    UnsupportedMarketDataCapabilityError,
)
from pyoptionpricer.pricing.requests import PricingRequest
from pyoptionpricer.pricing.results import PricingDiagnostics, PricingResult


class DiagnosticStatus(str, Enum):
    """Severity and outcome of one diagnostic check."""

    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


class DiagnosticCode(str, Enum):
    """Stable identifiers suitable for application-level branching."""

    CONTRACT_VALIDITY = "CONTRACT_VALIDITY"
    MARKET_QUOTE_VALIDITY = "MARKET_QUOTE_VALIDITY"
    QUOTE_FRESHNESS = "QUOTE_FRESHNESS"
    YIELD_CURVE_AVAILABILITY = "YIELD_CURVE_AVAILABILITY"
    VOLATILITY_AVAILABILITY = "VOLATILITY_AVAILABILITY"
    RISK_NEUTRAL_PROBABILITY = "RISK_NEUTRAL_PROBABILITY"
    NO_ARBITRAGE = "NO_ARBITRAGE"
    TREE_CONVERGENCE = "TREE_CONVERGENCE"
    PROVIDER_AUTHENTICATION = "PROVIDER_AUTHENTICATION"
    PROVIDER_DATA_AVAILABILITY = "PROVIDER_DATA_AVAILABILITY"
    PROVIDER_PAYLOAD = "PROVIDER_PAYLOAD"
    PROVIDER_CAPABILITY = "PROVIDER_CAPABILITY"
    PROVIDER_FAILURE = "PROVIDER_FAILURE"


@dataclass(frozen=True, slots=True)
class DiagnosticCheck:
    """One structured diagnostic outcome."""

    code: DiagnosticCode
    status: DiagnosticStatus
    message: str


@dataclass(frozen=True, slots=True)
class DiagnosticReport:
    """Collection of checks with a deterministic aggregate status."""

    checks: tuple[DiagnosticCheck, ...]

    @property
    def overall_status(self) -> DiagnosticStatus:
        statuses = {check.status for check in self.checks}
        if DiagnosticStatus.FAIL in statuses:
            return DiagnosticStatus.FAIL
        if DiagnosticStatus.WARN in statuses:
            return DiagnosticStatus.WARN
        return DiagnosticStatus.PASS

    def get(self, code: DiagnosticCode) -> DiagnosticCheck:
        """Return a check by stable code."""
        for check in self.checks:
            if check.code is code:
                return check
        raise KeyError(code.value)


def diagnose_pricing_result(
    request: PricingRequest,
    result: PricingResult,
    *,
    quote_stale_after: timedelta = timedelta(minutes=15),
) -> DiagnosticReport:
    """Evaluate data quality and model validity for a completed valuation."""
    if not isinstance(request, PricingRequest):
        raise TypeError("request must be a PricingRequest")
    if not isinstance(result, PricingResult):
        raise TypeError("result must be a PricingResult")
    if quote_stale_after <= timedelta(0):
        raise ValueError("quote_stale_after must be positive")
    if (
        result.model_parameters != request.model_parameters
        or result.inputs != request.inputs
        or result.valuation_datetime != request.market.valuation_datetime
        or result.currency is not request.instrument.currency
    ):
        raise ValueError("result does not belong to request")

    quote = request.market.option_quote
    if quote.bid is None or quote.ask is None:
        quote_check = DiagnosticCheck(
            DiagnosticCode.MARKET_QUOTE_VALIDITY,
            DiagnosticStatus.FAIL,
            "option quote requires both bid and ask",
        )
    else:
        quote_check = DiagnosticCheck(
            DiagnosticCode.MARKET_QUOTE_VALIDITY,
            DiagnosticStatus.PASS,
            "option quote is complete and internally consistent",
        )

    quote_age = request.market.valuation_datetime - quote.timestamp
    if quote_age < timedelta(0):
        freshness_check = DiagnosticCheck(
            DiagnosticCode.QUOTE_FRESHNESS,
            DiagnosticStatus.FAIL,
            "option quote timestamp is after valuation time",
        )
    elif quote_age > quote_stale_after:
        freshness_check = DiagnosticCheck(
            DiagnosticCode.QUOTE_FRESHNESS,
            DiagnosticStatus.WARN,
            f"option quote is stale by {quote_age}",
        )
    else:
        freshness_check = DiagnosticCheck(
            DiagnosticCode.QUOTE_FRESHNESS,
            DiagnosticStatus.PASS,
            "option quote is within the configured freshness threshold",
        )

    if isinstance(result.diagnostics, PricingDiagnostics):
        probability = result.diagnostics.tree_parameters.risk_neutral_probability
        probability_valid = isfinite(probability) and 0.0 <= probability <= 1.0
        probability_check = DiagnosticCheck(
            DiagnosticCode.RISK_NEUTRAL_PROBABILITY,
            DiagnosticStatus.PASS if probability_valid else DiagnosticStatus.FAIL,
            (
                "risk-neutral probability is within [0, 1]"
                if probability_valid
                else "risk-neutral probability is invalid"
            ),
        )
    else:
        probability_check = DiagnosticCheck(
            DiagnosticCode.RISK_NEUTRAL_PROBABILITY,
            DiagnosticStatus.PASS,
            "risk-neutral probability is not required by the analytical model",
        )

    no_arbitrage_valid = _satisfies_no_arbitrage(request, result)
    no_arbitrage_check = DiagnosticCheck(
        DiagnosticCode.NO_ARBITRAGE,
        DiagnosticStatus.PASS if no_arbitrage_valid else DiagnosticStatus.FAIL,
        (
            "model inputs and option value satisfy no-arbitrage bounds"
            if no_arbitrage_valid
            else "model inputs or option value violate no-arbitrage bounds"
        ),
    )

    return DiagnosticReport(
        (
            DiagnosticCheck(
                DiagnosticCode.CONTRACT_VALIDITY,
                DiagnosticStatus.PASS,
                "contract formed a valid pricing request",
            ),
            quote_check,
            freshness_check,
            DiagnosticCheck(
                DiagnosticCode.YIELD_CURVE_AVAILABILITY,
                DiagnosticStatus.PASS,
                "yield curve resolved a finite rate",
            ),
            DiagnosticCheck(
                DiagnosticCode.VOLATILITY_AVAILABILITY,
                DiagnosticStatus.PASS,
                "volatility resolved to a finite positive value",
            ),
            probability_check,
            no_arbitrage_check,
        )
    )


def diagnose_provider_error(error: MarketDataProviderError) -> DiagnosticCheck:
    """Map provider exceptions to stable application-level diagnostics."""
    if not isinstance(error, MarketDataProviderError):
        raise TypeError("error must be a MarketDataProviderError")
    if isinstance(error, MarketDataAuthenticationError):
        code = DiagnosticCode.PROVIDER_AUTHENTICATION
    elif isinstance(error, UnsupportedMarketDataCapabilityError):
        code = DiagnosticCode.PROVIDER_CAPABILITY
    elif isinstance(error, MalformedMarketDataError):
        code = DiagnosticCode.PROVIDER_PAYLOAD
    elif isinstance(error, MarketDataUnavailableError):
        code = DiagnosticCode.PROVIDER_DATA_AVAILABILITY
    else:
        code = DiagnosticCode.PROVIDER_FAILURE
    return DiagnosticCheck(code, DiagnosticStatus.FAIL, str(error))


def _satisfies_no_arbitrage(request: PricingRequest, result: PricingResult) -> bool:
    inputs = request.inputs
    if isinstance(result.diagnostics, PricingDiagnostics):
        tree = result.diagnostics.tree_parameters
        growth = exp(
            (inputs.risk_free_rate.value - inputs.dividend_yield.value)
            * tree.time_step
        )
        factor_condition = tree.down_factor <= growth <= tree.up_factor
    else:
        factor_condition = True

    spot = inputs.spot.value
    strike = inputs.strike.value
    maturity = inputs.maturity.value
    payoff = request.instrument.payoff
    if isinstance(request.instrument, BarrierOptionContract):
        vanilla_upper = (
            spot if request.instrument.option_type is OptionType.CALL else strike
        )
        upper = vanilla_upper + request.instrument.rebate
        tolerance = 1e-12 * max(1.0, upper)
        return factor_condition and -tolerance <= result.price <= upper + tolerance
    style = request.instrument.exercise_style
    has_early_exercise = style is not ExerciseStyle.EUROPEAN
    can_exercise_at_valuation = style is ExerciseStyle.AMERICAN or (
        style is ExerciseStyle.BERMUDAN
        and request.instrument.exercise_schedule is not None
        and request.market.valuation_datetime.date()
        in request.instrument.exercise_schedule.exercise_dates
    )
    if isinstance(payoff, CashOrNothingPayoff):
        if has_early_exercise:
            lower = payoff.value_at(spot) if can_exercise_at_valuation else 0.0
            upper = payoff.payout
        else:
            lower = 0.0
            upper = payoff.payout * exp(
                -inputs.risk_free_rate.value * maturity
            )
        tolerance = 1e-12 * max(1.0, upper)
        return factor_condition and lower - tolerance <= result.price <= upper + tolerance

    discounted_spot = spot * exp(-inputs.dividend_yield.value * maturity)
    discounted_strike = strike * exp(-inputs.risk_free_rate.value * maturity)
    if request.instrument.option_type is OptionType.CALL:
        lower = max(discounted_spot - discounted_strike, 0.0)
        upper = discounted_spot
    else:
        lower = max(discounted_strike - discounted_spot, 0.0)
        upper = discounted_strike
    if has_early_exercise:
        intrinsic = payoff.value_at(spot)
        if can_exercise_at_valuation:
            lower = max(lower, intrinsic)
        upper = spot if request.instrument.option_type is OptionType.CALL else strike
    tolerance = 1e-12 * max(1.0, upper)
    return factor_condition and lower - tolerance <= result.price <= upper + tolerance
