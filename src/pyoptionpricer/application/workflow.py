"""End-to-end application service for valuing one listed option contract."""

from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from enum import Enum
from math import isclose, isfinite

from pyoptionpricer.domain import (
    AssetClass,
    Currency,
    ExerciseStyle,
    OptionContract,
    VanillaOptionContract,
)
from pyoptionpricer.market import (
    DividendYield,
    EWMAVolatility,
    HistoricalVolatility,
    MarketDataUnavailableError,
    MarketImpliedVolatilitySurface,
    MarketObservation,
    MarketSnapshot,
    OptionQuote,
    VolatilityModel,
    YieldCurve,
)
from pyoptionpricer.market.data import (
    InstrumentReference,
    InstrumentReferenceProvider,
    InstrumentType,
    MarketDataProvider,
    MarketSegment,
    OptionChain,
    OptionChainEntry,
    OptionChainProvider,
)
from pyoptionpricer.models import PricingModel, PricingModelConfiguration
from pyoptionpricer.models.tree import CRRModelParameters
from pyoptionpricer.pricing import (
    CRRImpliedVolatilitySolver,
    DiagnosticReport,
    ImpliedVolatilityResult,
    MarketComparison,
    PricingEngineRegistry,
    PricingRequest,
    PricingResult,
    compare_to_market,
    diagnose_pricing_result,
)


class ContractResolutionError(ValueError):
    """Raised when a selection cannot resolve to one canonical option."""


class MarketDataSynchronizationError(ValueError):
    """Raised when observations cannot form one contemporaneous snapshot."""


class VolatilitySource(str, Enum):
    """Supported routes for selecting the pricing volatility."""

    PROVIDER = "provider"
    HISTORICAL = "historical"
    EWMA = "ewma"


@dataclass(frozen=True, slots=True)
class ContractSelection:
    """Provider identifiers plus optional canonical terms for one option.

    Providers with instrument-reference capability resolve the terms from
    their normalized instrument master. Providers without that capability,
    such as deterministic CSV files, require ``contract``.
    """

    underlying_id: str
    contract_id: str
    contract: OptionContract | None = None
    exercise_style: ExerciseStyle = ExerciseStyle.EUROPEAN

    def __post_init__(self) -> None:
        for name in ("underlying_id", "contract_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ContractResolutionError(f"{name} must be non-empty")
            object.__setattr__(self, name, value.strip())
        if self.contract is not None and not isinstance(self.contract, OptionContract):
            raise ContractResolutionError("contract must be an OptionContract")
        if not isinstance(self.exercise_style, ExerciseStyle):
            raise ContractResolutionError(
                "exercise_style must be an ExerciseStyle"
            )


@dataclass(frozen=True, slots=True)
class VolatilitySelection:
    """Configuration for market IV and an optional history fallback."""

    source: VolatilitySource = VolatilitySource.PROVIDER
    lookback: int = 60
    annualization_factor: float = 252.0
    ewma_decay: float = 0.94
    history_start: datetime | None = None
    fallback_source: VolatilitySource | None = None
    maximum_reliable_volatility: float = 5.0

    def __post_init__(self) -> None:
        if not isinstance(self.source, VolatilitySource):
            raise ValueError("source must be a VolatilitySource")
        if self.fallback_source not in {
            None,
            VolatilitySource.HISTORICAL,
            VolatilitySource.EWMA,
        }:
            raise ValueError("fallback_source must be historical, ewma, or None")
        if self.source is not VolatilitySource.PROVIDER and self.fallback_source:
            raise ValueError("fallback_source applies only to provider market IV")
        if (
            isinstance(self.maximum_reliable_volatility, bool)
            or not isinstance(self.maximum_reliable_volatility, (int, float))
            or not isfinite(self.maximum_reliable_volatility)
            or self.maximum_reliable_volatility <= 0
        ):
            raise ValueError(
                "maximum_reliable_volatility must be finite and positive"
            )


@dataclass(frozen=True, slots=True)
class SingleContractValuationRequest:
    """Application inputs for one reproducible end-to-end valuation."""

    selection: ContractSelection
    valuation_datetime: datetime
    model_parameters: PricingModelConfiguration = field(
        default_factory=CRRModelParameters
    )
    volatility: VolatilitySelection = field(default_factory=VolatilitySelection)
    yield_curve: YieldCurve | None = None
    dividend_data: DividendYield | None = None
    maximum_market_age: timedelta = timedelta(minutes=15)
    maximum_quote_skew: timedelta = timedelta(minutes=2)
    maximum_future_skew: timedelta = timedelta(seconds=30)

    def __post_init__(self) -> None:
        if not isinstance(self.selection, ContractSelection):
            raise TypeError("selection must be a ContractSelection")
        if not isinstance(self.valuation_datetime, datetime):
            raise TypeError("valuation_datetime must be a datetime")
        if (
            self.valuation_datetime.tzinfo is None
            or self.valuation_datetime.utcoffset() is None
        ):
            raise ValueError("valuation_datetime must be timezone-aware")
        if not isinstance(self.model_parameters, PricingModelConfiguration):
            raise TypeError(
                "model_parameters must implement PricingModelConfiguration"
            )
        if not isinstance(self.model_parameters.model, PricingModel):
            raise TypeError("model_parameters.model must be a PricingModel")
        if not isinstance(self.volatility, VolatilitySelection):
            raise TypeError("volatility must be a VolatilitySelection")
        if self.yield_curve is not None and not isinstance(
            self.yield_curve, YieldCurve
        ):
            raise TypeError("yield_curve must be a YieldCurve")
        if self.dividend_data is not None and not isinstance(
            self.dividend_data, DividendYield
        ):
            raise TypeError("dividend_data must be a DividendYield")
        if self.maximum_market_age <= timedelta(0):
            raise ValueError("maximum_market_age must be positive")
        if self.maximum_quote_skew <= timedelta(0):
            raise ValueError("maximum_quote_skew must be positive")
        if self.maximum_future_skew <= timedelta(0):
            raise ValueError("maximum_future_skew must be positive")


@dataclass(frozen=True, slots=True)
class SingleContractValuation:
    """Complete, presentation-independent output of the Sprint 10 workflow."""

    contract: OptionContract
    instrument_reference: InstrumentReference | None
    market_snapshot: MarketSnapshot
    pricing_request: PricingRequest
    pricing_result: PricingResult
    market_comparison: MarketComparison
    implied_volatility: ImpliedVolatilityResult
    diagnostics: DiagnosticReport
    volatility_surface: MarketImpliedVolatilitySurface | None = None
    used_volatility_fallback: bool = False


class CanonicalContractResolver:
    """Resolve provider references into the project's option domain model."""

    def resolve(
        self, provider: MarketDataProvider, selection: ContractSelection
    ) -> OptionContract:
        """Resolve only the domain contract for callers that do not need metadata."""
        return self.resolve_with_reference(provider, selection)[0]

    def resolve_with_reference(
        self, provider: MarketDataProvider, selection: ContractSelection
    ) -> tuple[OptionContract, InstrumentReference | None]:
        """Resolve a contract together with its normalized provider reference."""
        if isinstance(provider, InstrumentReferenceProvider):
            reference = provider.get_instrument(selection.contract_id)
            resolved = self._from_reference(reference, selection, provider)
            if selection.contract is not None:
                self._require_matching_terms(selection.contract, resolved)
                return selection.contract, reference
            return resolved, reference
        if selection.contract is None:
            raise ContractResolutionError(
                f"{type(provider).__name__} cannot resolve contract terms; "
                "supply a canonical OptionContract"
            )
        return selection.contract, None

    @staticmethod
    def _from_reference(
        reference: InstrumentReference,
        selection: ContractSelection,
        provider: InstrumentReferenceProvider,
    ) -> VanillaOptionContract:
        if reference.instrument_type is not InstrumentType.OPTION:
            raise ContractResolutionError(
                f"{selection.contract_id!r} does not identify an option"
            )
        underlying_id = selection.underlying_id
        if reference.underlying_id is not None:
            if reference.underlying_id != underlying_id:
                selected_underlying = provider.get_instrument(underlying_id)
                if selected_underlying.instrument_id != reference.underlying_id:
                    raise ContractResolutionError(
                        "selected underlying does not match the option "
                        "instrument reference"
                    )
            underlying_id = reference.underlying_id
        assert reference.strike is not None
        assert reference.expiry is not None
        assert reference.option_type is not None
        asset_class = (
            AssetClass.INDEX
            if reference.segment is MarketSegment.INDEX_DERIVATIVES
            else AssetClass.EQUITY
        )
        try:
            currency = Currency(reference.currency)
        except ValueError as error:
            raise ContractResolutionError(
                f"unsupported contract currency {reference.currency!r}"
            ) from error
        return VanillaOptionContract(
            underlying=underlying_id,
            strike=reference.strike,
            expiry=reference.expiry,
            option_type=reference.option_type,
            exercise_style=selection.exercise_style,
            asset_class=asset_class,
            exchange=reference.exchange,
            contract_symbol=reference.symbol,
            currency=currency,
        )

    @staticmethod
    def _require_matching_terms(
        supplied: OptionContract, resolved: VanillaOptionContract
    ) -> None:
        fields = ("strike", "expiry", "option_type", "currency")
        mismatches = [
            name
            for name in fields
            if getattr(supplied, name) != getattr(resolved, name)
        ]
        if mismatches:
            raise ContractResolutionError(
                "supplied contract conflicts with instrument reference: "
                + ", ".join(mismatches)
            )


class SingleContractValuationService:
    """Orchestrate normalized market data through all pricing services."""

    def __init__(
        self,
        provider: MarketDataProvider,
        *,
        implied_volatility_solver: CRRImpliedVolatilitySolver | None = None,
        contract_resolver: CanonicalContractResolver | None = None,
    ) -> None:
        if not isinstance(provider, MarketDataProvider):
            raise TypeError("provider must be a MarketDataProvider")
        self._provider = provider
        self._pricing_engine_registry = PricingEngineRegistry()
        self._implied_volatility_solver = (
            implied_volatility_solver or CRRImpliedVolatilitySolver()
        )
        self._contract_resolver = contract_resolver or CanonicalContractResolver()

    def value(
        self, request: SingleContractValuationRequest
    ) -> SingleContractValuation:
        if not isinstance(request, SingleContractValuationRequest):
            raise TypeError("request must be a SingleContractValuationRequest")

        selection = request.selection
        valuation_time = request.valuation_datetime
        contract, instrument_reference = (
            self._contract_resolver.resolve_with_reference(self._provider, selection)
        )
        spot = self._provider.get_spot(selection.underlying_id, valuation_time)
        quote, volatility, volatility_surface, used_fallback = (
            self._market_quote_and_volatility(
                request,
                contract,
                instrument_reference,
            )
        )
        valuation_time = self._synchronized_valuation_time(
            spot, quote.timestamp, request
        )
        if valuation_time != request.valuation_datetime:
            request = replace(request, valuation_datetime=valuation_time)
        yield_curve = request.yield_curve or self._provider.get_yield_curve(
            contract.currency.value, valuation_time
        )
        dividend_data = request.dividend_data or self._provider.get_dividend_data(
            selection.underlying_id, valuation_time
        )
        snapshot = MarketSnapshot(
            valuation_datetime=valuation_time,
            spot=spot,
            option_quote=quote,
            yield_curve=yield_curve,
            dividend_data=dividend_data,
            volatility_input=volatility,
        )
        pricing_request = PricingRequest(
            contract,
            snapshot,
            request.model_parameters,
            contract_source=(
                f"{instrument_reference.vendor}:INSTRUMENT_REFERENCE"
                if instrument_reference is not None
                else "option_contract"
            ),
        )
        pricing_result = self._pricing_engine_registry.price(pricing_request)
        comparison = compare_to_market(pricing_result.price, quote)
        implied_volatility = self._implied_volatility_solver.solve(pricing_request)
        diagnostics = diagnose_pricing_result(pricing_request, pricing_result)
        return SingleContractValuation(
            contract=contract,
            instrument_reference=instrument_reference,
            market_snapshot=snapshot,
            pricing_request=pricing_request,
            pricing_result=pricing_result,
            market_comparison=comparison,
            implied_volatility=implied_volatility,
            diagnostics=diagnostics,
            volatility_surface=volatility_surface,
            used_volatility_fallback=used_fallback,
        )

    def _market_quote_and_volatility(
        self,
        request: SingleContractValuationRequest,
        contract: OptionContract,
        instrument_reference: InstrumentReference | None,
    ) -> tuple[
        OptionQuote,
        MarketObservation[float],
        MarketImpliedVolatilitySurface | None,
        bool,
    ]:
        selection = request.volatility
        if (
            selection.source is VolatilitySource.PROVIDER
            and isinstance(self._provider, OptionChainProvider)
        ):
            try:
                chain = self._provider.get_option_chain(
                    request.selection.underlying_id,
                    contract.expiry,
                    request.valuation_datetime,
                )
                entry = self._target_chain_entry(
                    chain, contract, instrument_reference
                )
                surface = MarketImpliedVolatilitySurface.from_option_chain(
                    chain,
                    request.valuation_datetime,
                    maximum_reliable_volatility=(
                        selection.maximum_reliable_volatility
                    ),
                )
                volatility = surface.volatility(
                    contract.strike, contract.expiry, contract.option_type
                )
                return entry.quote, volatility, surface, False
            except MarketDataUnavailableError:
                if selection.fallback_source is None:
                    raise
                quote = self._provider.get_option_quote(
                    request.selection.contract_id, request.valuation_datetime
                )
                volatility = self._estimate_volatility(
                    request, selection.fallback_source
                )
                return quote, volatility, None, True

        quote = self._provider.get_option_quote(
            request.selection.contract_id, request.valuation_datetime
        )
        if selection.source is VolatilitySource.PROVIDER:
            volatility = self._provider.get_volatility_input(
                request.selection.underlying_id, request.valuation_datetime
            )
        else:
            volatility = self._estimate_volatility(request, selection.source)
        return quote, volatility, None, False

    @staticmethod
    def _target_chain_entry(
        chain: OptionChain,
        contract: OptionContract,
        instrument_reference: InstrumentReference | None,
    ) -> OptionChainEntry:
        contract_id = (
            instrument_reference.instrument_id
            if instrument_reference is not None
            else None
        )
        matches = tuple(
            entry
            for entry in chain.entries
            if (
                (contract_id is None or entry.contract_id == contract_id)
                and entry.expiry == contract.expiry
                and isclose(entry.strike, contract.strike, rel_tol=1e-12)
                and entry.option_type is contract.option_type
            )
        )
        if len(matches) != 1:
            raise MarketDataUnavailableError(
                "option chain does not contain exactly one target contract"
            )
        return matches[0]

    @staticmethod
    def _synchronized_valuation_time(
        spot: MarketObservation[float],
        option_timestamp: datetime,
        request: SingleContractValuationRequest,
    ) -> datetime:
        valuation_time = request.valuation_datetime
        observations = {
            "underlying quote": spot.timestamp,
            "option quote": option_timestamp,
        }
        for name, timestamp in observations.items():
            age = valuation_time - timestamp
            if age < timedelta(0):
                if -age > request.maximum_future_skew:
                    raise MarketDataSynchronizationError(
                        f"{name} timestamp is after the valuation time by {-age}; "
                        f"maximum capture skew is {request.maximum_future_skew}"
                    )
                continue
            if age > request.maximum_market_age:
                raise MarketDataSynchronizationError(
                    f"{name} is stale by {age}; maximum age is "
                    f"{request.maximum_market_age}"
                )
        skew = abs(spot.timestamp - option_timestamp)
        if skew > request.maximum_quote_skew:
            raise MarketDataSynchronizationError(
                f"underlying and option quotes differ by {skew}; maximum skew is "
                f"{request.maximum_quote_skew}"
            )
        return max(valuation_time, spot.timestamp, option_timestamp)

    def _estimate_volatility(
        self,
        request: SingleContractValuationRequest,
        source: VolatilitySource,
    ) -> MarketObservation[float]:
        selection = request.volatility
        model: VolatilityModel
        if source is VolatilitySource.HISTORICAL:
            model = HistoricalVolatility(
                lookback=selection.lookback,
                annualization_factor=selection.annualization_factor,
            )
        else:
            model = EWMAVolatility(
                lookback=selection.lookback,
                decay=selection.ewma_decay,
                annualization_factor=selection.annualization_factor,
            )
        history_start = selection.history_start or (
            request.valuation_datetime
            - timedelta(days=max(selection.lookback * 3, selection.lookback + 1))
        )
        history = self._provider.get_price_history(
            request.selection.underlying_id,
            history_start,
            request.valuation_datetime,
        )
        estimate = model.estimate(history)
        sources = sorted({point.source for point in history})
        datasets = sorted(
            {point.dataset for point in history if point.dataset is not None}
        )
        retrieved = [
            point.retrieved_at for point in history if point.retrieved_at is not None
        ]
        return MarketObservation(
            value=estimate,
            timestamp=max(point.timestamp for point in history),
            source="+".join(sources),
            field=f"{source.value}_annualized_volatility",
            dataset="+".join(datasets) if datasets else None,
            retrieved_at=max(retrieved) if retrieved else None,
        )
