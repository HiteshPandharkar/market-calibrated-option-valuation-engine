"""Framework-independent flow used by the Streamlit presentation layer.

This module translates UI values into application requests and translates
application results into presentation data.  It deliberately contains no
Streamlit imports so the UI framework never becomes part of the pricing
architecture.
"""

from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, fields
from datetime import date, datetime
from pathlib import Path
from typing import Any

from pyoptionpricer.application import (
    ContractSelection,
    MarketDataProviderConfiguration,
    MarketDataProviderFactory,
    MarketDataProviderName,
    ProviderConfigurationError,
    SingleContractValuation,
    SingleContractValuationRequest,
    SingleContractValuationService,
    VolatilitySelection,
    VolatilitySource,
)
from pyoptionpricer.domain import (
    AssetClass,
    Currency,
    ExerciseStyle,
    OptionContract,
    OptionType,
)
from pyoptionpricer.market import (
    ContinuousDividendYield,
    FlatYieldCurve,
    MalformedMarketDataError,
    MarketDataAuthenticationError,
    MarketDataProvider,
    MarketDataProviderError,
    MarketDataUnavailableError,
    MarketObservation,
    UnsupportedMarketDataCapabilityError,
)
from pyoptionpricer.market.data import (
    InstrumentReference,
    InstrumentReferenceProvider,
    InstrumentType,
)
from pyoptionpricer.models.tree import CRRModelParameters


@dataclass(frozen=True, slots=True)
class ValuationForm:
    """UI values needed to request one application-level valuation."""

    provider: MarketDataProviderName
    underlying_id: str
    contract_id: str
    valuation_datetime: datetime
    steps: int = 200
    volatility_source: VolatilitySource = VolatilitySource.PROVIDER
    volatility_fallback: VolatilitySource | None = None
    lookback: int = 60
    ewma_decay: float = 0.94
    exercise_style: ExerciseStyle = ExerciseStyle.EUROPEAN
    risk_free_rate: float | None = None
    dividend_yield: float | None = None
    strike: float | None = None
    expiry: date | None = None
    option_type: OptionType | None = None
    asset_class: AssetClass = AssetClass.EQUITY
    exchange: str | None = None
    currency: Currency = Currency.INR


@dataclass(frozen=True, slots=True)
class InstrumentChoice:
    """Canonical lookup result with a vendor-neutral display label."""

    instrument_id: str
    label: str
    instrument_type: InstrumentType
    underlying_id: str | None = None
    expiry: date | None = None
    strike: float | None = None
    option_type: OptionType | None = None


@dataclass(frozen=True, slots=True)
class UserFacingFailure:
    """Sanitized failure suitable for rendering to an end user."""

    title: str
    message: str


ServiceFactory = Callable[[MarketDataProvider], SingleContractValuationService]


class ValuationUIFlow:
    """Thin, framework-neutral adapter over application services."""

    def __init__(
        self,
        provider_factory: MarketDataProviderFactory | None = None,
        service_factory: ServiceFactory = SingleContractValuationService,
    ) -> None:
        self._provider_factory = provider_factory or MarketDataProviderFactory()
        self._service_factory = service_factory

    def create_provider(
        self,
        provider: MarketDataProviderName,
        *,
        csv_data_directory: str | Path | None = None,
        environment: Mapping[str, str] | None = None,
    ) -> MarketDataProvider:
        """Construct the selected provider through application configuration."""
        return self._provider_factory.create(
            MarketDataProviderConfiguration(
                provider=provider,
                csv_data_directory=csv_data_directory,
                environment=environment,
            )
        )

    @staticmethod
    def search_underlyings(
        provider: MarketDataProvider, query: str
    ) -> tuple[InstrumentChoice, ...]:
        """Return canonical underlying choices from a capable provider."""
        reference_provider = _reference_provider(provider)
        references = reference_provider.search_instruments(query)
        return tuple(
            _choice(reference)
            for reference in references
            if reference.instrument_type in {InstrumentType.EQUITY, InstrumentType.INDEX}
        )

    @staticmethod
    def contracts_for_underlying(
        provider: MarketDataProvider, underlying_id: str
    ) -> tuple[InstrumentChoice, ...]:
        """Return canonical option contracts for one selected underlying."""
        reference_provider = _reference_provider(provider)
        underlying = reference_provider.get_instrument(underlying_id)
        references = reference_provider.search_instruments(underlying.symbol)
        contracts = (
            reference
            for reference in references
            if reference.instrument_type is InstrumentType.OPTION
            and reference.underlying_id == underlying.instrument_id
        )
        return tuple(
            _choice(reference)
            for reference in sorted(
                contracts,
                key=lambda item: (
                    item.expiry or date.max,
                    item.strike or 0.0,
                    item.option_type.value if item.option_type else "",
                ),
            )
        )

    def value(
        self, provider: MarketDataProvider, form: ValuationForm
    ) -> SingleContractValuation:
        """Build an application request and delegate the complete valuation."""
        request = self.build_request(form)
        return self._service_factory(provider).value(request)

    @staticmethod
    def build_request(form: ValuationForm) -> SingleContractValuationRequest:
        """Translate presentation values without reimplementing domain validation."""
        contract = _manual_contract(form)
        assumption_source = "UI_ASSUMPTION"
        rate = (
            FlatYieldCurve(
                form.risk_free_rate,
                MarketObservation(
                    form.risk_free_rate,
                    form.valuation_datetime,
                    assumption_source,
                    "continuous_zero_rate",
                ),
            )
            if form.risk_free_rate is not None
            else None
        )
        dividend = (
            ContinuousDividendYield(
                form.dividend_yield,
                MarketObservation(
                    form.dividend_yield,
                    form.valuation_datetime,
                    assumption_source,
                    "continuous_dividend_yield",
                ),
            )
            if form.dividend_yield is not None
            else None
        )
        return SingleContractValuationRequest(
            selection=ContractSelection(
                form.underlying_id,
                form.contract_id,
                contract=contract,
                exercise_style=form.exercise_style,
            ),
            valuation_datetime=form.valuation_datetime,
            model_parameters=CRRModelParameters(form.steps),
            volatility=VolatilitySelection(
                source=form.volatility_source,
                lookback=form.lookback,
                ewma_decay=form.ewma_decay,
                fallback_source=form.volatility_fallback,
            ),
            yield_curve=rate,
            dividend_data=dividend,
        )


def present_valuation(valuation: SingleContractValuation) -> dict[str, Any]:
    """Return canonical, presentation-ready sections for a completed valuation."""
    result = valuation.pricing_result
    quote = valuation.market_snapshot.option_quote
    comparison = valuation.market_comparison
    contract = valuation.contract
    return {
        "contract": {
            "Symbol": contract.contract_symbol or contract.underlying,
            "Underlying": contract.underlying,
            "Expiry": contract.expiry.isoformat(),
            "Strike": contract.strike,
            "Option type": contract.option_type.value,
            "Exercise style": contract.exercise_style.value,
            "Currency": contract.currency.value,
        },
        "market": {
            "Spot": valuation.market_snapshot.spot.value,
            "Bid": quote.bid,
            "Ask": quote.ask,
            "Midpoint": quote.mid(),
            "Last": quote.last,
            "Quote time": quote.timestamp.isoformat(),
            "Source": source_label(quote.source),
        },
        "model": {
            "Model": result.model_name,
            "Tree steps": result.model_parameters.steps,
            "Volatility source": result.inputs.volatility.method,
            "Volatility": result.inputs.volatility.value,
            "Risk-free rate": result.inputs.risk_free_rate.value,
            "Dividend yield": result.inputs.dividend_yield.value,
        },
        "valuation": {
            "Theoretical value": result.price,
            "Market midpoint": comparison.market_mid,
            "Absolute difference": comparison.absolute_difference,
            "Percentage difference": comparison.percentage_difference,
            "Calibrated implied volatility": (
                valuation.implied_volatility.implied_volatility
            ),
            "Calibration residual": valuation.implied_volatility.pricing_residual,
        },
        "greeks": asdict(result.greeks),
        "diagnostics": [
            {
                "Code": check.code.value,
                "Status": check.status.value,
                "Message": check.message,
            }
            for check in valuation.diagnostics.checks
        ],
        "provenance": [
            {
                "Input": name.replace("_", " ").title(),
                "Value": trace.value,
                "Source": source_label(trace.source),
                "Field": trace.field,
                "Method": trace.method,
                "Observation time": (
                    trace.observation_timestamp.isoformat()
                    if trace.observation_timestamp is not None
                    else None
                ),
            }
            for item in fields(result.inputs)
            for name, trace in ((item.name, getattr(result.inputs, item.name)),)
        ],
    }


def user_facing_failure(error: Exception) -> UserFacingFailure:
    """Translate known failures without leaking credentials or raw payloads."""
    if isinstance(error, MarketDataAuthenticationError):
        return UserFacingFailure(
            "Provider authentication failed",
            "Check the configured provider session and try again. Credentials are not displayed.",
        )
    if isinstance(error, MalformedMarketDataError):
        return UserFacingFailure(
            "Provider data could not be normalized",
            "The provider returned data that does not satisfy the canonical market-data contract.",
        )
    if isinstance(error, UnsupportedMarketDataCapabilityError):
        return UserFacingFailure(
            "Data capability unavailable",
            "The selected provider cannot supply one of the requested valuation inputs.",
        )
    if isinstance(error, MarketDataUnavailableError):
        return UserFacingFailure(
            "Market data unavailable",
            "No usable market observation was available for the selected contract and time.",
        )
    if isinstance(error, (ProviderConfigurationError, MarketDataProviderError)):
        return UserFacingFailure(
            "Provider configuration failed",
            "Check the selected provider configuration and session settings, then try again.",
        )
    if isinstance(error, (TypeError, ValueError)):
        return UserFacingFailure("Invalid valuation request", str(error))
    return UserFacingFailure(
        "Valuation failed",
        "The valuation could not be completed. Review the inputs and try again.",
    )


def source_label(source: str | None) -> str:
    """Format provenance as a friendly source name, never as a vendor key."""
    if source is None:
        return "Not available"
    if source.upper() == "UPSTOX":
        return "Upstox"
    return source


def _reference_provider(provider: MarketDataProvider) -> InstrumentReferenceProvider:
    if not isinstance(provider, InstrumentReferenceProvider):
        raise UnsupportedMarketDataCapabilityError(
            f"{type(provider).__name__} does not support instrument lookup"
        )
    return provider


def _choice(reference: InstrumentReference) -> InstrumentChoice:
    return InstrumentChoice(
        instrument_id=reference.instrument_id,
        label=f"{reference.display_symbol} - {reference.exchange}",
        instrument_type=reference.instrument_type,
        underlying_id=reference.underlying_id,
        expiry=reference.expiry,
        strike=reference.strike,
        option_type=reference.option_type,
    )


def _manual_contract(form: ValuationForm) -> OptionContract | None:
    supplied = (form.strike, form.expiry, form.option_type)
    if form.provider is not MarketDataProviderName.CSV:
        return None
    if any(value is None for value in supplied):
        raise ValueError("CSV valuations require strike, expiry, and option type")
    assert form.strike is not None
    assert form.expiry is not None
    assert form.option_type is not None
    return OptionContract(
        underlying=form.underlying_id,
        strike=form.strike,
        expiry=form.expiry,
        option_type=form.option_type,
        exercise_style=form.exercise_style,
        asset_class=form.asset_class,
        exchange=form.exchange,
        contract_symbol=form.contract_id,
        currency=form.currency,
    )
