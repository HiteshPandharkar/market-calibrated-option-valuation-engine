"""Provider-neutral contract for estimating annualized volatility."""

from abc import ABC, abstractmethod
from collections.abc import Iterable
from enum import Enum
from typing import TypeAlias

from pyoptionpricer.market.data.models import HistoricalBar
from pyoptionpricer.market.observation import MarketObservation


PriceHistoryPoint: TypeAlias = MarketObservation[float] | HistoricalBar


class ReturnConvention(str, Enum):
    """Convention used to transform adjacent prices into returns."""

    LOG = "LOG"


class VolatilityModel(ABC):
    """Estimate annualized volatility from normalized price history."""

    @abstractmethod
    def estimate(self, history: Iterable[PriceHistoryPoint]) -> float:
        """Return annualized volatility as a decimal (for example, 0.20)."""

