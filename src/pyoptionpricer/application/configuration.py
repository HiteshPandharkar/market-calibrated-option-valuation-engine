"""Configuration-driven construction of market-data providers."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from pyoptionpricer.market.data import CSVMarketDataProvider, MarketDataProvider
from pyoptionpricer.market.data.providers.upstox import UpstoxMarketDataProvider


class ProviderConfigurationError(ValueError):
    """Raised when an application provider configuration is incomplete."""


class MarketDataProviderName(str, Enum):
    """Market-data providers supported by the application composition root."""

    CSV = "csv"
    UPSTOX = "upstox"


@dataclass(frozen=True, slots=True)
class MarketDataProviderConfiguration:
    """Inputs needed to select and construct one provider.

    ``environment`` is used only by providers whose sessions are configured
    from environment-style key/value pairs. It is intentionally explicit so
    tests and callers do not need to mutate process-global state.
    """

    provider: MarketDataProviderName | str
    csv_data_directory: str | Path | None = None
    environment: Mapping[str, str] | None = None

    def __post_init__(self) -> None:
        if isinstance(self.provider, str):
            try:
                object.__setattr__(
                    self,
                    "provider",
                    MarketDataProviderName(self.provider.strip().lower()),
                )
            except ValueError as error:
                raise ProviderConfigurationError(
                    f"unsupported market-data provider {self.provider!r}"
                ) from error
        if not isinstance(self.provider, MarketDataProviderName):
            raise ProviderConfigurationError(
                "provider must identify a market-data provider"
            )
        if self.provider is MarketDataProviderName.CSV:
            if self.csv_data_directory is None:
                raise ProviderConfigurationError(
                    "csv_data_directory is required for the CSV provider"
                )
        elif self.csv_data_directory is not None:
            raise ProviderConfigurationError(
                "csv_data_directory may only be supplied for the CSV provider"
            )


ProviderBuilder = Callable[[MarketDataProviderConfiguration], MarketDataProvider]


class MarketDataProviderFactory:
    """Construct providers through a small, replaceable registry."""

    def __init__(
        self,
        builders: Mapping[MarketDataProviderName, ProviderBuilder] | None = None,
    ) -> None:
        self._builders = dict(builders or self._default_builders())

    def create(
        self, configuration: MarketDataProviderConfiguration
    ) -> MarketDataProvider:
        if not isinstance(configuration, MarketDataProviderConfiguration):
            raise TypeError(
                "configuration must be a MarketDataProviderConfiguration"
            )
        try:
            builder = self._builders[configuration.provider]
        except KeyError as error:
            raise ProviderConfigurationError(
                "no provider builder is registered for "
                f"{configuration.provider.value!r}"
            ) from error
        provider = builder(configuration)
        if not isinstance(provider, MarketDataProvider):
            raise ProviderConfigurationError(
                f"builder for {configuration.provider.value!r} returned an "
                "invalid provider"
            )
        return provider

    @staticmethod
    def _default_builders() -> dict[MarketDataProviderName, ProviderBuilder]:
        def csv_builder(
            configuration: MarketDataProviderConfiguration,
        ) -> MarketDataProvider:
            assert configuration.csv_data_directory is not None
            return CSVMarketDataProvider(configuration.csv_data_directory)

        def upstox_builder(
            configuration: MarketDataProviderConfiguration,
        ) -> MarketDataProvider:
            return UpstoxMarketDataProvider.from_env(configuration.environment)

        return {
            MarketDataProviderName.CSV: csv_builder,
            MarketDataProviderName.UPSTOX: upstox_builder,
        }
