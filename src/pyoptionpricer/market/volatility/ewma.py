"""Exponentially weighted moving-average volatility estimator."""

from collections.abc import Iterable
from dataclasses import dataclass
from math import isfinite, sqrt

from pyoptionpricer.market.exceptions import InvalidVolatilityInputError
from pyoptionpricer.market.volatility._returns import log_returns, validate_configuration
from pyoptionpricer.market.volatility.volatility_model import (
    PriceHistoryPoint,
    ReturnConvention,
    VolatilityModel,
)


@dataclass(frozen=True, slots=True)
class EWMAVolatility(VolatilityModel):
    """Annualized RiskMetrics-style EWMA of squared log returns.

    The first squared return initializes the variance. Each later return uses
    ``variance = decay * previous_variance + (1 - decay) * return_squared``.
    ``lookback`` counts returns and ``annualization_factor`` is observations
    per year.
    """

    lookback: int = 20
    decay: float = 0.94
    annualization_factor: float = 252.0
    return_convention: ReturnConvention = ReturnConvention.LOG

    def __post_init__(self) -> None:
        validate_configuration(
            self.lookback,
            self.annualization_factor,
            self.return_convention,
            minimum_lookback=1,
        )
        if (
            isinstance(self.decay, bool)
            or not isinstance(self.decay, (int, float))
            or not isfinite(float(self.decay))
            or not 0 < self.decay < 1
        ):
            raise InvalidVolatilityInputError(
                "decay must be finite and strictly between 0 and 1"
            )

    def estimate(self, history: Iterable[PriceHistoryPoint]) -> float:
        returns = log_returns(history, self.lookback)
        variance = returns[0] ** 2
        for value in returns[1:]:
            variance = self.decay * variance + (1.0 - self.decay) * value**2
        return sqrt(variance * self.annualization_factor)

