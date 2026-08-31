"""Market-implied volatility surfaces built from normalized option chains."""

from dataclasses import dataclass
from datetime import date, datetime
from math import isclose, isfinite, sqrt
from numbers import Real

from pyoptionpricer.domain import OptionType
from pyoptionpricer.market.data.models import OptionChain
from pyoptionpricer.market.exceptions import MarketDataUnavailableError
from pyoptionpricer.market.observation import MarketObservation


@dataclass(frozen=True, slots=True)
class MarketIVPoint:
    """A reliable vendor IV at one strike and expiry."""

    expiry: date
    strike: float
    option_type: OptionType
    observation: MarketObservation[float]

    def __post_init__(self) -> None:
        if not isinstance(self.expiry, date):
            raise TypeError("expiry must be a date")
        if (
            isinstance(self.strike, bool)
            or not isinstance(self.strike, Real)
            or not isfinite(float(self.strike))
            or self.strike <= 0
        ):
            raise ValueError("strike must be finite and positive")
        if not isinstance(self.option_type, OptionType):
            raise TypeError("option_type must be an OptionType")
        if not isinstance(self.observation, MarketObservation):
            raise TypeError("observation must be a MarketObservation")
        if (
            isinstance(self.observation.value, bool)
            or not isinstance(self.observation.value, Real)
            or not isfinite(float(self.observation.value))
        ):
            raise ValueError("observation value must be finite and numeric")


class MarketImpliedVolatilitySurface:
    """Interpolate normalized vendor IVs without depending on a vendor schema.

    Strike interpolation is linear. Expiry interpolation is linear in total
    variance, a stable convention that preserves non-negative forward variance
    when the input surface is well formed. Extrapolation is deliberately not
    performed because it would turn missing market evidence into a silent model
    assumption.
    """

    def __init__(
        self,
        valuation_datetime: datetime,
        points: tuple[MarketIVPoint, ...],
        *,
        maximum_reliable_volatility: float = 5.0,
    ) -> None:
        if valuation_datetime.tzinfo is None or valuation_datetime.utcoffset() is None:
            raise ValueError("valuation_datetime must be timezone-aware")
        if (
            isinstance(maximum_reliable_volatility, bool)
            or not isinstance(maximum_reliable_volatility, Real)
            or not isfinite(float(maximum_reliable_volatility))
            or maximum_reliable_volatility <= 0
        ):
            raise ValueError("maximum_reliable_volatility must be finite and positive")
        reliable = tuple(
            point
            for point in points
            if (
                isfinite(float(point.observation.value))
                and 0 < float(point.observation.value) <= maximum_reliable_volatility
                and point.expiry > valuation_datetime.date()
            )
        )
        if not reliable:
            raise MarketDataUnavailableError(
                "option chain contains no reliable positive vendor implied volatilities"
            )
        keys = [(point.expiry, point.strike, point.option_type) for point in reliable]
        if len(keys) != len(set(keys)):
            raise ValueError("surface points must be unique by expiry, strike, and type")
        self._valuation_datetime = valuation_datetime
        self._points = reliable

    @classmethod
    def from_option_chain(
        cls,
        chain: OptionChain,
        valuation_datetime: datetime,
        *,
        maximum_reliable_volatility: float = 5.0,
    ) -> "MarketImpliedVolatilitySurface":
        points = tuple(
            MarketIVPoint(
                entry.expiry,
                entry.strike,
                entry.option_type,
                entry.vendor_implied_volatility,
            )
            for entry in chain.entries
            if entry.vendor_implied_volatility is not None
        )
        return cls(
            valuation_datetime,
            points,
            maximum_reliable_volatility=maximum_reliable_volatility,
        )

    @property
    def points(self) -> tuple[MarketIVPoint, ...]:
        return self._points

    def volatility(
        self, strike: float, expiry: date, option_type: OptionType
    ) -> MarketObservation[float]:
        if (
            isinstance(strike, bool)
            or not isinstance(strike, Real)
            or not isfinite(float(strike))
            or strike <= 0
        ):
            raise ValueError("strike must be finite and positive")
        if expiry <= self._valuation_datetime.date():
            raise ValueError("expiry must be after the valuation date")
        expiry_points = sorted(
            {
                point.expiry
                for point in self._points
                if point.option_type is option_type
            }
        )
        if not expiry_points:
            raise MarketDataUnavailableError(
                f"surface has no reliable {option_type.value} implied volatilities"
            )
        if expiry in expiry_points:
            value, observations = self._strike_volatility(
                strike, expiry, option_type
            )
        else:
            lower, upper = self._bracket(expiry_points, expiry, "expiry")
            lower_iv, lower_observations = self._strike_volatility(
                strike, lower, option_type
            )
            upper_iv, upper_observations = self._strike_volatility(
                strike, upper, option_type
            )
            lower_time = self._year_fraction(lower)
            upper_time = self._year_fraction(upper)
            target_time = self._year_fraction(expiry)
            weight = (target_time - lower_time) / (upper_time - lower_time)
            total_variance = (
                (1.0 - weight) * lower_iv * lower_iv * lower_time
                + weight * upper_iv * upper_iv * upper_time
            )
            value = sqrt(total_variance / target_time)
            observations = lower_observations + upper_observations
        return self._observation(value, observations)

    def _strike_volatility(
        self, strike: float, expiry: date, option_type: OptionType
    ) -> tuple[float, tuple[MarketObservation[float], ...]]:
        points = sorted(
            (
                point
                for point in self._points
                if point.expiry == expiry and point.option_type is option_type
            ),
            key=lambda point: point.strike,
        )
        exact = next(
            (
                point
                for point in points
                if isclose(point.strike, strike, rel_tol=1e-12)
            ),
            None,
        )
        if exact is not None:
            return (
                float(exact.observation.value),
                (exact.observation,),
            )
        lower_strike, upper_strike = self._bracket(
            [point.strike for point in points], strike, "strike"
        )
        lower = next(point for point in points if point.strike == lower_strike)
        upper = next(point for point in points if point.strike == upper_strike)
        weight = (strike - lower.strike) / (upper.strike - lower.strike)
        value = (1.0 - weight) * float(lower.observation.value) + weight * float(
            upper.observation.value
        )
        return (
            value,
            (lower.observation, upper.observation),
        )

    @staticmethod
    def _bracket(values: list[float] | list[date], target: float | date, axis: str):
        lower = [value for value in values if value < target]
        upper = [value for value in values if value > target]
        if not lower or not upper:
            raise MarketDataUnavailableError(
                f"cannot interpolate {axis} outside the reliable IV surface"
            )
        return max(lower), min(upper)

    def _year_fraction(self, expiry: date) -> float:
        return (expiry - self._valuation_datetime.date()).days / 365.0

    @staticmethod
    def _observation(
        value: float,
        observations: tuple[MarketObservation[float], ...],
    ) -> MarketObservation[float]:
        sources = sorted({observation.source for observation in observations})
        datasets = sorted(
            {
                observation.dataset
                for observation in observations
                if observation.dataset is not None
            }
        )
        retrieved = tuple(
            observation.retrieved_at
            for observation in observations
            if observation.retrieved_at is not None
        )
        return MarketObservation(
            value=value,
            timestamp=max(observation.timestamp for observation in observations),
            source="+".join(sources),
            field="market_implied_volatility",
            dataset="+".join(datasets) if datasets else None,
            retrieved_at=max(retrieved) if retrieved else None,
        )
