from pathlib import Path

import pytest

from pyoptionpricer.application import (
    MarketDataProviderConfiguration,
    MarketDataProviderFactory,
    MarketDataProviderName,
    ProviderConfigurationError,
)
from pyoptionpricer.market.data import CSVMarketDataProvider


FIXTURES = Path(__file__).parents[2] / "fixtures" / "market_data"


def test_factory_selects_csv_provider_from_configuration() -> None:
    provider = MarketDataProviderFactory().create(
        MarketDataProviderConfiguration(
            MarketDataProviderName.CSV, csv_data_directory=FIXTURES
        )
    )

    assert isinstance(provider, CSVMarketDataProvider)


def test_external_string_configuration_is_normalized() -> None:
    configuration = MarketDataProviderConfiguration(
        "CSV", csv_data_directory=FIXTURES
    )

    assert configuration.provider is MarketDataProviderName.CSV


def test_csv_configuration_requires_data_directory() -> None:
    with pytest.raises(ProviderConfigurationError, match="csv_data_directory"):
        MarketDataProviderConfiguration(MarketDataProviderName.CSV)


def test_factory_registry_is_an_extension_point() -> None:
    expected = CSVMarketDataProvider(FIXTURES)
    factory = MarketDataProviderFactory(
        {MarketDataProviderName.UPSTOX: lambda configuration: expected}
    )

    actual = factory.create(
        MarketDataProviderConfiguration(MarketDataProviderName.UPSTOX)
    )

    assert actual is expected
