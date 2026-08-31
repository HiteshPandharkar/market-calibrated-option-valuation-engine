"""Errors raised by normalized market-data domain models."""


class MarketDataValidationError(ValueError):
    """Base error for invalid normalized market data."""


class InvalidMarketObservationError(MarketDataValidationError):
    """Raised when an observation or its provenance is invalid."""


class InvalidMarketQuoteError(MarketDataValidationError):
    """Raised when an option quote violates market-data invariants."""


class InvalidMarketSnapshotError(MarketDataValidationError):
    """Raised when a market snapshot is incomplete or inconsistent."""


class InvalidCurveError(MarketDataValidationError):
    """Raised when a yield or dividend curve violates its contract."""


class InvalidVolatilityInputError(MarketDataValidationError):
    """Raised when a volatility model or its price history is invalid."""


class MarketDataProviderError(Exception):
    """Base error for failures at a market-data provider boundary."""


class MarketDataAuthenticationError(MarketDataProviderError):
    """Raised when a provider rejects or cannot use its credentials."""


class MarketDataUnavailableError(MarketDataProviderError):
    """Raised when a provider has no observation matching a request."""


class MalformedMarketDataError(MarketDataProviderError):
    """Raised when provider input cannot be mapped to domain models."""


class UnsupportedMarketDataCapabilityError(MarketDataProviderError):
    """Raised when a provider cannot supply a requested data capability."""
