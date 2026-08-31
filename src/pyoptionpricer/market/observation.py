"""Provenance-bearing normalized market observations."""

from dataclasses import dataclass
from datetime import datetime
from typing import Generic, TypeVar

from pyoptionpricer.market._validation import (
    require_aware_datetime,
    require_non_empty_text,
)
from pyoptionpricer.market.exceptions import InvalidMarketObservationError

ObservationValue = TypeVar("ObservationValue")


@dataclass(frozen=True, slots=True)
class MarketObservation(Generic[ObservationValue]):
    """A normalized value together with its source provenance.

    ``timestamp`` is when the source says the value applied. ``retrieved_at``
    records when the project obtained it; it defaults to ``timestamp`` for
    deterministic files that do not carry a separate retrieval time.
    """

    value: ObservationValue
    timestamp: datetime
    source: str
    field: str
    dataset: str | None = None
    retrieved_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.value is None:
            raise InvalidMarketObservationError("value must not be None")
        require_aware_datetime(
            self.timestamp, "timestamp", InvalidMarketObservationError
        )
        require_non_empty_text(self.source, "source", InvalidMarketObservationError)
        require_non_empty_text(self.field, "field", InvalidMarketObservationError)

        if self.dataset is not None:
            require_non_empty_text(
                self.dataset, "dataset", InvalidMarketObservationError
            )
        if self.retrieved_at is not None:
            require_aware_datetime(
                self.retrieved_at, "retrieved_at", InvalidMarketObservationError
            )

    @property
    def source_vendor(self) -> str:
        """Canonical provenance name for the observation source."""
        return self.source

    @property
    def source_dataset(self) -> str | None:
        """Canonical provenance name for the optional source dataset."""
        return self.dataset

    @property
    def source_field(self) -> str:
        """Canonical provenance name for the source field."""
        return self.field

    @property
    def source_timestamp(self) -> datetime:
        """Canonical provenance name for the source timestamp."""
        return self.timestamp
