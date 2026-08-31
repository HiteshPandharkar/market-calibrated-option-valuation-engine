"""Close-to-close historical volatility estimator."""

from collections.abc import Iterable
from dataclasses import dataclass
from math import sqrt
from statistics import stdev

from pyoptionpricer.market.volatility._returns import log_returns, validate_configuration
from pyoptionpricer.market.volatility.volatility_model import (
    PriceHistoryPoint,
    ReturnConvention,
    VolatilityModel,
)


@dataclass(frozen=True, slots=True)
class HistoricalVolatility(VolatilityModel):
    """Annualized sample standard deviation of close-to-close log returns.

    ``lookback`` counts returns, so estimating a 20-return window requires
    21 prices. ``annualization_factor`` is the assumed observations per year.
    """

    lookback: int = 20
    annualization_factor: float = 252.0
    return_convention: ReturnConvention = ReturnConvention.LOG

    def __post_init__(self) -> None:
        validate_configuration(
            self.lookback,
            self.annualization_factor,
            self.return_convention,
            minimum_lookback=2,
        )

    def estimate(self, history: Iterable[PriceHistoryPoint]) -> float:
        returns = log_returns(history, self.lookback)
        return stdev(returns) * sqrt(self.annualization_factor)

