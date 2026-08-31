"""Provider contracts for retrieving normalized market data."""

from abc import ABC, abstractmethod
from datetime import datetime

from pyoptionpricer.market.curves import DividendYield, YieldCurve
from pyoptionpricer.market.observation import MarketObservation
from pyoptionpricer.market.quote import OptionQuote
from pyoptionpricer.market.snapshot import MarketSnapshot


class MarketDataProvider(ABC):
    """Vendor-neutral source of the inputs needed for a V1 snapshot."""

    @abstractmethod
    def get_spot(
        self, symbol: str, timestamp: datetime
    ) -> MarketObservation[float]:
        """Return the latest spot observation at or before ``timestamp``."""

    @abstractmethod
    def get_option_quote(self, contract_id: str, timestamp: datetime) -> OptionQuote:
        """Return the latest option quote at or before ``timestamp``."""

    @abstractmethod
    def get_price_history(
        self, symbol: str, start: datetime, end: datetime
    ) -> tuple[MarketObservation[float], ...]:
        """Return close observations in the inclusive time interval."""

    @abstractmethod
    def get_yield_curve(
        self, currency: str, timestamp: datetime
    ) -> YieldCurve:
        """Return a continuously compounded zero curve."""

    @abstractmethod
    def get_dividend_data(
        self, symbol: str, timestamp: datetime
    ) -> DividendYield:
        """Return the V1 continuous dividend-yield input."""

    @abstractmethod
    def get_volatility_input(
        self, symbol: str, timestamp: datetime
    ) -> MarketObservation[float]:
        """Return the volatility observation selected for V1 pricing."""

    def build_snapshot(
        self,
        symbol: str,
        contract_id: str,
        currency: str,
        valuation_datetime: datetime,
    ) -> MarketSnapshot:
        """Assemble normalized provider results without exposing raw payloads."""
        return MarketSnapshot(
            valuation_datetime=valuation_datetime,
            spot=self.get_spot(symbol, valuation_datetime),
            option_quote=self.get_option_quote(contract_id, valuation_datetime),
            yield_curve=self.get_yield_curve(currency, valuation_datetime),
            dividend_data=self.get_dividend_data(symbol, valuation_datetime),
            volatility_input=self.get_volatility_input(symbol, valuation_datetime),
        )

    def get_snapshot(
        self,
        symbol: str,
        contract_id: str,
        currency: str,
        valuation_datetime: datetime,
    ) -> MarketSnapshot:
        """Compatibility alias expressing snapshot retrieval as a query."""
        return self.build_snapshot(symbol, contract_id, currency, valuation_datetime)
