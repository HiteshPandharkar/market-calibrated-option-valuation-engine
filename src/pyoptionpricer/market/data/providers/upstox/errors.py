"""Project-level errors translated from Upstox integration failures."""

from pyoptionpricer.market.exceptions import (
    MalformedMarketDataError,
    MarketDataAuthenticationError,
    MarketDataProviderError,
    MarketDataUnavailableError,
)


class UpstoxProviderError(MarketDataProviderError):
    """Base error raised by the Upstox adapter."""


class UpstoxConfigurationError(UpstoxProviderError):
    """Raised when required environment-based configuration is invalid."""


class UpstoxAuthenticationError(UpstoxProviderError, MarketDataAuthenticationError):
    """Raised when Upstox rejects or cannot use the configured session."""


class UpstoxAPIError(UpstoxProviderError, MarketDataUnavailableError):
    """Raised when an Upstox request fails outside authentication."""


class UpstoxPayloadError(UpstoxProviderError, MalformedMarketDataError):
    """Raised when an Upstox response cannot be mapped safely."""
