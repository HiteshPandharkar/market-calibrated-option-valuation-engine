"""Complete pricing requests assembled from normalized market snapshots."""

from dataclasses import dataclass, field
from datetime import datetime
from math import isfinite

from pyoptionpricer.domain import OptionContract
from pyoptionpricer.market import MarketObservation, MarketSnapshot
from pyoptionpricer.models import (
    ModelSelection,
    PricingModel,
    PricingModelConfiguration,
)
from pyoptionpricer.models.tree import CRRModelParameters


class InvalidPricingRequestError(ValueError):
    """Raised when a contract and snapshot cannot form a complete request."""


@dataclass(frozen=True, slots=True)
class InputProvenance:
    """A resolved numerical input and the route by which it was obtained."""

    value: float
    source: str
    field: str
    method: str
    observation_timestamp: datetime | None = None


@dataclass(frozen=True, slots=True)
class PricingInputs:
    """Traceable values consumed by the numerical model."""

    spot: InputProvenance
    strike: InputProvenance
    maturity: InputProvenance
    risk_free_rate: InputProvenance
    dividend_yield: InputProvenance
    volatility: InputProvenance


@dataclass(frozen=True, slots=True)
class PricingRequest:
    """A contract, normalized market state, and model-specific configuration."""

    instrument: OptionContract
    market: MarketSnapshot
    model_parameters: PricingModelConfiguration = field(
        default_factory=CRRModelParameters
    )
    contract_source: str = "option_contract"
    inputs: PricingInputs = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.instrument, OptionContract):
            raise InvalidPricingRequestError("instrument must be an OptionContract")
        if not isinstance(self.market, MarketSnapshot):
            raise InvalidPricingRequestError("market must be a MarketSnapshot")
        if not isinstance(self.model_parameters, PricingModelConfiguration):
            raise InvalidPricingRequestError(
                "model_parameters must implement PricingModelConfiguration"
            )
        if not isinstance(self.model_parameters.model, PricingModel):
            raise InvalidPricingRequestError(
                "model_parameters.model must be a PricingModel"
            )
        if not isinstance(self.contract_source, str) or not self.contract_source.strip():
            raise InvalidPricingRequestError("contract_source must be non-empty")
        object.__setattr__(self, "contract_source", self.contract_source.strip())
        object.__setattr__(self, "inputs", self._resolve_inputs())

    @property
    def model(self) -> PricingModel:
        """Return the canonical model selected by the configuration type."""
        return self.model_parameters.model

    @property
    def model_selection(self) -> ModelSelection:
        """Expose the selected model and its isolated configuration together."""
        return ModelSelection(self.model, self.model_parameters)

    def _resolve_inputs(self) -> PricingInputs:
        maturity_days = (self.instrument.expiry - self.market.valuation_datetime.date()).days
        maturity = maturity_days / 365.0
        if maturity <= 0:
            raise InvalidPricingRequestError("contract must expire after the valuation date")
        if self.market.yield_curve is None:
            raise InvalidPricingRequestError("market snapshot requires a yield curve")
        if self.market.dividend_data is None:
            raise InvalidPricingRequestError("market snapshot requires dividend data")
        if self.market.volatility_input is None:
            raise InvalidPricingRequestError("market snapshot requires volatility input")

        rate = self.market.yield_curve.zero_rate(maturity)
        dividend = self.market.dividend_data.continuous_rate(maturity)
        volatility = self._volatility_trace(self.market.volatility_input)
        for name, value in (("risk-free rate", rate), ("dividend yield", dividend)):
            if not isfinite(value):
                raise InvalidPricingRequestError(f"resolved {name} must be finite")

        return PricingInputs(
            spot=self._observation_trace(self.market.spot, "direct observation"),
            strike=InputProvenance(
                self.instrument.strike,
                self.contract_source,
                "strike",
                "resolved contract term",
            ),
            maturity=InputProvenance(
                maturity,
                f"{self.contract_source}+market_snapshot",
                "expiry-valuation_datetime",
                "Actual/365 Fixed",
            ),
            risk_free_rate=self._curve_trace(
                rate, self.market.yield_curve, "zero_rate", "maturity interpolation"
            ),
            dividend_yield=self._curve_trace(
                dividend,
                self.market.dividend_data,
                "continuous_rate",
                "continuous yield at maturity",
            ),
            volatility=volatility,
        )

    @staticmethod
    def _observation_trace(
        observation: MarketObservation[float], method: str
    ) -> InputProvenance:
        return InputProvenance(
            float(observation.value),
            observation.source,
            observation.field,
            method,
            observation.timestamp,
        )

    @classmethod
    def _volatility_trace(cls, value: object) -> InputProvenance:
        if isinstance(value, MarketObservation):
            try:
                trace = cls._observation_trace(
                    value,
                    (
                        "market IV surface selection"
                        if value.field == "market_implied_volatility"
                        else "selected volatility observation"
                    ),
                )
            except (TypeError, ValueError) as error:
                raise InvalidPricingRequestError(
                    "volatility observation must contain a number"
                ) from error
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            trace = InputProvenance(
                float(value),
                "market_snapshot",
                "volatility_input",
                "explicit model assumption",
            )
        else:
            raise InvalidPricingRequestError(
                "volatility input must be a number or MarketObservation"
            )
        if not isfinite(trace.value) or trace.value <= 0:
            raise InvalidPricingRequestError("volatility must be finite and positive")
        return trace

    @staticmethod
    def _curve_trace(value: float, curve: object, field: str, method: str) -> InputProvenance:
        observations = getattr(curve, "observations", ())
        observation = getattr(curve, "observation", None)
        if observation is None and observations:
            observation = observations[0]
        if isinstance(observation, MarketObservation):
            return InputProvenance(
                float(value),
                observation.source,
                field,
                method,
                observation.timestamp,
            )
        return InputProvenance(
            float(value), type(curve).__name__, field, method
        )
