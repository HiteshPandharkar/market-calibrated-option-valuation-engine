"""Environment-based Upstox session configuration."""

from collections.abc import Mapping
from dataclasses import dataclass, field
import os

from pyoptionpricer.market.data.providers.upstox.errors import UpstoxConfigurationError

DEFAULT_API_BASE_URL = "https://api.upstox.com"
DEFAULT_INSTRUMENTS_URL = (
    "https://assets.upstox.com/market-quote/instruments/exchange/complete.json.gz"
)


@dataclass(frozen=True, slots=True)
class UpstoxConfiguration:
    """Credentials and endpoints required by an Upstox HTTP session."""

    access_token: str = field(repr=False)
    api_base_url: str = DEFAULT_API_BASE_URL
    instruments_url: str = DEFAULT_INSTRUMENTS_URL
    timeout_seconds: float = 10.0

    def __post_init__(self) -> None:
        if not isinstance(self.access_token, str) or not self.access_token.strip():
            raise UpstoxConfigurationError(
                "UPSTOX_ACCESS_TOKEN must be set to a non-empty access token"
            )
        if not self.api_base_url.startswith("https://"):
            raise UpstoxConfigurationError("Upstox API base URL must use HTTPS")
        if not self.instruments_url.startswith("https://"):
            raise UpstoxConfigurationError("Upstox instruments URL must use HTTPS")
        if self.timeout_seconds <= 0:
            raise UpstoxConfigurationError("Upstox timeout must be positive")

    @classmethod
    def from_env(
        cls, environ: Mapping[str, str] | None = None
    ) -> "UpstoxConfiguration":
        """Load a short-lived access token without reading a secrets file."""
        values = os.environ if environ is None else environ
        timeout_text = values.get("UPSTOX_TIMEOUT_SECONDS", "10")
        try:
            timeout = float(timeout_text)
        except ValueError as error:
            raise UpstoxConfigurationError(
                "UPSTOX_TIMEOUT_SECONDS must be a number"
            ) from error
        return cls(
            access_token=values.get("UPSTOX_ACCESS_TOKEN", ""),
            api_base_url=values.get("UPSTOX_API_BASE_URL", DEFAULT_API_BASE_URL),
            instruments_url=values.get(
                "UPSTOX_INSTRUMENTS_URL", DEFAULT_INSTRUMENTS_URL
            ),
            timeout_seconds=timeout,
        )
