from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from pyoptionpricer.market import InvalidMarketObservationError, MarketObservation


TIMESTAMP = datetime(2026, 8, 28, 15, 29, tzinfo=UTC)


def test_observation_preserves_value_timestamp_and_provenance() -> None:
    retrieved_at = datetime(2026, 8, 28, 15, 30, tzinfo=UTC)

    observation = MarketObservation(
        value=1387.20,
        timestamp=TIMESTAMP,
        source="UPSTOX",
        field="last_price",
        dataset="MARKET_QUOTE",
        retrieved_at=retrieved_at,
    )

    assert observation.value == 1387.20
    assert observation.timestamp is TIMESTAMP
    assert observation.source_vendor == "UPSTOX"
    assert observation.source_dataset == "MARKET_QUOTE"
    assert observation.source_field == "last_price"
    assert observation.source_timestamp is TIMESTAMP
    assert observation.retrieved_at is retrieved_at


def test_observation_is_immutable() -> None:
    observation = MarketObservation(1387.20, TIMESTAMP, "UPSTOX", "last_price")

    with pytest.raises(FrozenInstanceError):
        observation.value = 1400.0  # type: ignore[misc]


@pytest.mark.parametrize("value", [None])
def test_observation_rejects_missing_value(value: object) -> None:
    with pytest.raises(InvalidMarketObservationError, match="must not be None"):
        MarketObservation(value, TIMESTAMP, "UPSTOX", "last_price")


@pytest.mark.parametrize("field_name", ["source", "field"])
def test_observation_rejects_missing_provenance(field_name: str) -> None:
    arguments = {"source": "UPSTOX", "field": "last_price"}
    arguments[field_name] = "  "

    with pytest.raises(InvalidMarketObservationError, match=field_name):
        MarketObservation(1387.20, TIMESTAMP, **arguments)


def test_observation_rejects_naive_timestamp() -> None:
    with pytest.raises(InvalidMarketObservationError, match="timezone-aware"):
        MarketObservation(
            1387.20,
            datetime(2026, 8, 28, 15, 29),
            "UPSTOX",
            "last_price",
        )
