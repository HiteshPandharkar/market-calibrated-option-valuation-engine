"""Reproducible normalized market snapshots."""

from dataclasses import dataclass
from datetime import datetime

from pyoptionpricer.market._validation import (
    require_aware_datetime,
    require_finite_number,
)
from pyoptionpricer.market.curves import DividendYield, YieldCurve
from pyoptionpricer.market.exceptions import InvalidMarketSnapshotError
from pyoptionpricer.market.observation import MarketObservation
from pyoptionpricer.market.quote import OptionQuote


@dataclass(frozen=True, slots=True)
class MarketSnapshot:
    """Normalized inputs captured for a reproducible valuation.

    Yield and dividend inputs expose maturity-aware project-owned contracts.
    Volatility may be a provider observation or an estimate produced by a
    project-owned volatility model; Sprint 5 selects it for pricing.
    """

    valuation_datetime: datetime
    spot: MarketObservation[float]
    option_quote: OptionQuote
    yield_curve: YieldCurve | None = None
    dividend_data: DividendYield | None = None
    volatility_input: object | None = None

    def __post_init__(self) -> None:
        require_aware_datetime(
            self.valuation_datetime,
            "valuation_datetime",
            InvalidMarketSnapshotError,
        )
        if not isinstance(self.spot, MarketObservation):
            raise InvalidMarketSnapshotError(
                "spot must be a provenance-bearing MarketObservation"
            )
        require_finite_number(self.spot.value, "spot.value", InvalidMarketSnapshotError)
        if self.spot.value <= 0:
            raise InvalidMarketSnapshotError("spot.value must be positive")
        if not isinstance(self.option_quote, OptionQuote):
            raise InvalidMarketSnapshotError("option_quote must be an OptionQuote")
        if self.yield_curve is not None and not isinstance(
            self.yield_curve, YieldCurve
        ):
            raise InvalidMarketSnapshotError("yield_curve must be a YieldCurve")
        if self.dividend_data is not None and not isinstance(
            self.dividend_data, DividendYield
        ):
            raise InvalidMarketSnapshotError("dividend_data must be a DividendYield")
