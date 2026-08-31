import json
from datetime import UTC, datetime
import os
from pathlib import Path
from typing import Any

import pytest

from pyoptionpricer.application import (
    MarketDataProviderFactory,
    MarketDataProviderName,
    MarketDataSynchronizationError,
)
from pyoptionpricer.cli import main
from pyoptionpricer.market.data.providers.upstox import (
    UpstoxAPIError,
    UpstoxMarketDataProvider,
)


FIXTURES = Path(__file__).parents[2] / "fixtures" / "upstox"
UPSTOX_TIME = datetime(2026, 8, 28, 10, 0, tzinfo=UTC)
UNDERLYING_ID = "NSE_EQ|INE002A01018"
OPTION_ID = "NSE_FO|50001"
PROJECT_ROOT = Path(__file__).parents[3]


def _load_live_environment() -> dict[str, str]:
    """Load process variables with a local, git-ignored .env fallback."""
    values = dict(os.environ)
    path = PROJECT_ROOT / ".env"
    if not path.is_file():
        return values

    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line.removeprefix("export ").strip()
        if "=" not in line:
            continue
        name, raw_value = line.split("=", 1)
        name = name.strip()
        value = raw_value.strip()
        if (
            len(value) >= 2
            and value[0] == value[-1]
            and value[0] in {'"', "'"}
        ):
            value = value[1:-1]
        if name and name not in values:
            values[name] = value
    return values


def _required_live_setting(environment: dict[str, str], name: str) -> str:
    value = environment.get(name, "").strip()
    if not value:
        pytest.skip(f"{name} is required for the live CLI test")
    return value


class FixtureUpstoxClient:
    def _load(self, filename: str) -> Any:
        with (FIXTURES / filename).open(encoding="utf-8") as stream:
            return json.load(stream)

    def fetch_instruments(self) -> list[dict[str, Any]]:
        return self._load("instruments.json")

    def fetch_full_quote(self, vendor_instrument_id: str) -> dict[str, Any]:
        return self._load("full_market_quote.json")

    def fetch_historical_candles(
        self, vendor_instrument_id: str, from_date: str, to_date: str
    ) -> dict[str, Any]:
        return self._load("historical_candles_60.json")

    def fetch_option_chain(
        self, vendor_underlying_id: str, expiry_date: str
    ) -> dict[str, Any]:
        return self._load("option_chain.json")


def test_sample_cli_runs_complete_workflow(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(
        [
            "--provider",
            "csv",
            "--data-directory",
            "tests/fixtures/market_data",
            "--underlying-id",
            "ACME",
            "--contract-id",
            "ACME-20261231-1400-C",
            "--valuation-time",
            "2026-08-28T15:30:00+00:00",
            "--strike",
            "1400",
            "--expiry",
            "2026-12-31",
            "--type",
            "CALL",
            "--exchange",
            "SAMPLE_EXCHANGE",
            "--steps",
            "200",
        ]
    )

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["price"] == 83.41348229842129
    assert output["market_comparison"]["market_mid"] == 35.35
    assert output["diagnostic_status"] == "PASS"
    assert output["inputs"]["spot"]["source"] == "SAMPLE_EXCHANGE"


def test_upstox_cli_runs_complete_workflow_from_normalized_fixtures(
    capsys: pytest.CaptureFixture[str],
) -> None:
    provider = UpstoxMarketDataProvider(
        FixtureUpstoxClient(), clock=lambda: UPSTOX_TIME
    )
    provider_factory = MarketDataProviderFactory(
        {MarketDataProviderName.UPSTOX: lambda configuration: provider}
    )

    exit_code = main(
        [
            "--provider",
            "upstox",
            "--underlying-id",
            UNDERLYING_ID,
            "--contract-id",
            OPTION_ID,
            "--valuation-time",
            "2026-08-28T10:00:00+00:00",
            "--steps",
            "200",
            "--risk-free-rate",
            "0.065",
            "--dividend-yield",
            "0.012",
        ],
        provider_factory=provider_factory,
    )

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["contract"]["symbol"] == "RELIANCE 29 SEP 26 1400 CE"
    assert output["contract"]["strike"] == 1400.0
    assert output["contract"]["expiry"] == "2026-09-29"
    assert output["price"] > 0
    assert output["greeks"]["delta"] > 0
    assert output["market_comparison"]["market_mid"] == 35.35
    assert output["diagnostic_status"] == "PASS"
    assert output["implied_volatility"]["market_midpoint"] == 35.35
    assert output["implied_volatility"]["calibrated_price"] == pytest.approx(
        35.35, abs=1e-6
    )
    assert output["inputs"]["spot"]["source"] == "UPSTOX"
    assert output["inputs"]["volatility"]["source"] == "UPSTOX"
    assert output["inputs"]["volatility"]["field"] == "market_implied_volatility"
    assert output["inputs"]["volatility"]["value"] == pytest.approx(
        0.225
    )
    assert output["market_iv_surface"]["point_count"] == 1
    assert output["market_iv_surface"]["used_volatility_fallback"] is False
    assert output["inputs"]["strike"]["source"] == (
        "UPSTOX:INSTRUMENT_REFERENCE"
    )
    assert output["inputs"]["risk_free_rate"]["source"] == "CLI_ASSUMPTION"


@pytest.mark.live_upstox
def test_upstox_cli_loads_local_environment_and_runs_live_workflow(
    capsys: pytest.CaptureFixture[str],
) -> None:
    environment = _load_live_environment()
    if environment.get("UPSTOX_RUN_LIVE_TESTS") != "1":
        pytest.skip("set UPSTOX_RUN_LIVE_TESTS=1 to run live Upstox tests")

    access_token = _required_live_setting(environment, "UPSTOX_ACCESS_TOKEN")
    underlying_key = _required_live_setting(
        environment, "UPSTOX_TEST_INSTRUMENT_KEY"
    )
    option_key = _required_live_setting(
        environment, "UPSTOX_TEST_OPTION_INSTRUMENT_KEY"
    )
    risk_free_rate = _required_live_setting(
        environment, "UPSTOX_TEST_RISK_FREE_RATE"
    )
    dividend_yield = _required_live_setting(
        environment, "UPSTOX_TEST_DIVIDEND_YIELD"
    )
    assert access_token
    valuation_time = datetime.now(UTC)

    try:
        exit_code = main(
            [
                "--provider",
                "upstox",
                "--underlying-id",
                underlying_key,
                "--contract-id",
                option_key,
                "--valuation-time",
                valuation_time.isoformat(),
                "--steps",
                "200",
                "--risk-free-rate",
                risk_free_rate,
                "--dividend-yield",
                dividend_yield,
            ],
            environment=environment,
        )
    except MarketDataSynchronizationError as error:
        pytest.skip(f"live market is not contemporaneous: {error}")
    except UpstoxAPIError as error:
        pytest.skip(f"live Upstox API is unavailable: {error}")

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["inputs"]["spot"]["source"] == "UPSTOX"
    assert output["inputs"]["volatility"]["source"] == "UPSTOX"
    assert output["inputs"]["volatility"]["field"] == "market_implied_volatility"
    assert output["market_iv_surface"]["point_count"] > 0
    assert output["implied_volatility"]["calibrated_price"] == pytest.approx(
        output["market_comparison"]["market_mid"], abs=1e-6
    )
