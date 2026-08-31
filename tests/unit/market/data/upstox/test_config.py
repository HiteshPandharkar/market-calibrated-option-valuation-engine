import pytest

from pyoptionpricer.market.data.providers.upstox import (
    UpstoxConfiguration,
    UpstoxConfigurationError,
)


def test_configuration_reads_access_token_from_environment_mapping() -> None:
    configuration = UpstoxConfiguration.from_env(
        {"UPSTOX_ACCESS_TOKEN": "secret-token", "UPSTOX_TIMEOUT_SECONDS": "5"}
    )

    assert configuration.access_token == "secret-token"
    assert configuration.timeout_seconds == 5.0
    assert "secret-token" not in repr(configuration)


def test_configuration_requires_access_token() -> None:
    with pytest.raises(UpstoxConfigurationError, match="UPSTOX_ACCESS_TOKEN"):
        UpstoxConfiguration.from_env({})


def test_configuration_rejects_non_https_endpoint() -> None:
    with pytest.raises(UpstoxConfigurationError, match="HTTPS"):
        UpstoxConfiguration("token", api_base_url="http://example.test")
