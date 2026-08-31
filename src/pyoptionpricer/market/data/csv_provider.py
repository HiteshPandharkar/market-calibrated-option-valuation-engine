"""Deterministic CSV-backed implementation of the market-data contract."""

from collections.abc import Iterable, Mapping
import csv
from datetime import datetime
from math import isfinite
from pathlib import Path
from typing import Final

from pyoptionpricer.market.curves import (
    ContinuousDividendYield,
    DividendYield,
    FlatYieldCurve,
    InterpolatedYieldCurve,
    YieldCurve,
)
from pyoptionpricer.market.data.provider import MarketDataProvider
from pyoptionpricer.market.exceptions import (
    MalformedMarketDataError,
    MarketDataUnavailableError,
    MarketDataValidationError,
)
from pyoptionpricer.market.observation import MarketObservation
from pyoptionpricer.market.quote import OptionQuote

_PROVENANCE_FIELDS: Final = frozenset(
    {"timestamp", "source", "dataset", "retrieved_at"}
)


class CSVMarketDataProvider(MarketDataProvider):
    """Read canonical project data from a directory of CSV files.

    Each point-in-time lookup uses as-of semantics: the newest matching row
    whose timestamp does not exceed the requested timestamp is returned.
    """

    def __init__(self, data_directory: str | Path) -> None:
        self._data_directory = Path(data_directory)
        if not self._data_directory.is_dir():
            raise MarketDataUnavailableError(
                f"CSV data directory does not exist: {self._data_directory}"
            )

    def get_spot(
        self, symbol: str, timestamp: datetime
    ) -> MarketObservation[float]:
        row = self._as_of_row(
            "spots.csv", "symbol", symbol, timestamp, {"price", *_PROVENANCE_FIELDS}
        )
        observation = self._observation(row, "spots.csv", "price")
        if observation.value <= 0:
            raise self._malformed("spots.csv", row, "price must be positive")
        return observation

    def get_option_quote(self, contract_id: str, timestamp: datetime) -> OptionQuote:
        filename = "option_quotes.csv"
        row = self._as_of_row(
            filename,
            "contract_id",
            contract_id,
            timestamp,
            {"timestamp", "bid", "ask", "last"},
        )
        try:
            return OptionQuote(
                bid=self._optional_float(row, filename, "bid"),
                ask=self._optional_float(row, filename, "ask"),
                last=self._optional_float(row, filename, "last"),
                timestamp=self._timestamp(row, filename, "timestamp"),
                source=row.get("source", "").strip() or "CSV",
                dataset=row.get("dataset", "").strip() or filename,
                retrieved_at=(
                    self._parse_datetime(
                        row["retrieved_at"].strip(),
                        filename,
                        row,
                        "retrieved_at",
                    )
                    if row.get("retrieved_at", "").strip()
                    else None
                ),
            )
        except MarketDataValidationError as error:
            raise self._malformed(filename, row, str(error)) from error

    def get_price_history(
        self, symbol: str, start: datetime, end: datetime
    ) -> tuple[MarketObservation[float], ...]:
        self._require_aware(start, "start")
        self._require_aware(end, "end")
        if start > end:
            raise ValueError("start must not be after end")

        filename = "price_history.csv"
        rows = self._read_rows(
            filename, {"symbol", "close", *_PROVENANCE_FIELDS}
        )
        matching = [
            row
            for row in rows
            if row["symbol"] == symbol
            and start <= self._timestamp(row, filename, "timestamp") <= end
        ]
        if not matching:
            raise MarketDataUnavailableError(
                f"{filename}: no data for symbol={symbol!r} between "
                f"{start.isoformat()} and {end.isoformat()}"
            )
        matching.sort(key=lambda row: self._timestamp(row, filename, "timestamp"))
        observations = tuple(
            self._observation(row, filename, "close") for row in matching
        )
        for row, observation in zip(matching, observations, strict=True):
            if observation.value <= 0:
                raise self._malformed(filename, row, "close must be positive")
        return observations

    def get_yield_curve(
        self, currency: str, timestamp: datetime
    ) -> YieldCurve:
        filename = "yield_curves.csv"
        self._require_aware(timestamp, "timestamp")
        rows = self._read_rows(
            filename, {"currency", "rate", *_PROVENANCE_FIELDS}
        )
        matching = [
            row
            for row in rows
            if row["currency"] == currency
            and self._timestamp(row, filename, "timestamp") <= timestamp
        ]
        if not matching:
            raise MarketDataUnavailableError(
                f"{filename}: no data for currency={currency!r} at or before "
                f"{timestamp.isoformat()}"
            )
        latest_timestamp = max(
            self._timestamp(row, filename, "timestamp") for row in matching
        )
        latest = [
            row
            for row in matching
            if self._timestamp(row, filename, "timestamp") == latest_timestamp
        ]
        observations = tuple(
            self._observation(row, filename, "rate") for row in latest
        )

        maturity_column_present = all("maturity_years" in row for row in latest)
        maturity_values_present = maturity_column_present and all(
            row["maturity_years"].strip() for row in latest
        )
        if not maturity_values_present:
            if len(latest) != 1:
                raise MalformedMarketDataError(
                    f"{filename}: multiple flat rates for currency={currency!r} "
                    f"at {latest_timestamp.isoformat()}"
                )
            return FlatYieldCurve(observations[0].value, observations[0])

        pillars = sorted(
            zip(
                (
                    self._required_float(row, filename, "maturity_years")
                    for row in latest
                ),
                observations,
                strict=True,
            ),
            key=lambda item: item[0],
        )
        try:
            return InterpolatedYieldCurve(
                maturities=tuple(item[0] for item in pillars),
                rates=tuple(item[1].value for item in pillars),
                observations=tuple(item[1] for item in pillars),
            )
        except MarketDataValidationError as error:
            raise MalformedMarketDataError(f"{filename}: {error}") from error

    def get_dividend_data(
        self, symbol: str, timestamp: datetime
    ) -> DividendYield:
        filename = "dividends.csv"
        row = self._as_of_row(
            filename,
            "symbol",
            symbol,
            timestamp,
            {"dividend_yield", *_PROVENANCE_FIELDS},
        )
        observation = self._observation(row, filename, "dividend_yield")
        try:
            return ContinuousDividendYield(observation.value, observation)
        except MarketDataValidationError as error:
            raise self._malformed(filename, row, str(error)) from error

    def get_volatility_input(
        self, symbol: str, timestamp: datetime
    ) -> MarketObservation[float]:
        filename = "volatility.csv"
        row = self._as_of_row(
            filename,
            "symbol",
            symbol,
            timestamp,
            {"volatility", *_PROVENANCE_FIELDS},
        )
        observation = self._observation(row, filename, "volatility")
        if observation.value < 0:
            raise self._malformed(filename, row, "volatility must not be negative")
        return observation

    def _as_of_row(
        self,
        filename: str,
        key_field: str,
        key: str,
        timestamp: datetime,
        required_fields: set[str],
    ) -> Mapping[str, str]:
        self._require_aware(timestamp, "timestamp")
        rows = self._read_rows(filename, {key_field, *required_fields})
        matching = [
            row
            for row in rows
            if row[key_field] == key
            and self._timestamp(row, filename, "timestamp") <= timestamp
        ]
        if not matching:
            raise MarketDataUnavailableError(
                f"{filename}: no data for {key_field}={key!r} at or before "
                f"{timestamp.isoformat()}"
            )

        latest_timestamp = max(
            self._timestamp(row, filename, "timestamp") for row in matching
        )
        latest = [
            row
            for row in matching
            if self._timestamp(row, filename, "timestamp") == latest_timestamp
        ]
        if len(latest) > 1:
            raise MalformedMarketDataError(
                f"{filename}: duplicate rows for {key_field}={key!r} at "
                f"{latest_timestamp.isoformat()}"
            )
        return latest[0]

    def _read_rows(
        self, filename: str, required_fields: Iterable[str]
    ) -> list[dict[str, str]]:
        path = self._data_directory / filename
        try:
            with path.open(encoding="utf-8-sig", newline="") as stream:
                reader = csv.DictReader(stream)
                headers = set(reader.fieldnames or ())
                missing = set(required_fields) - headers
                if missing:
                    fields = ", ".join(sorted(missing))
                    raise MalformedMarketDataError(
                        f"{filename}: missing required column(s): {fields}"
                    )
                rows = []
                for row_number, row in enumerate(reader, start=2):
                    if None in row:
                        raise MalformedMarketDataError(
                            f"{filename} row {row_number}: too many columns"
                        )
                    if any(value is None for value in row.values()):
                        raise MalformedMarketDataError(
                            f"{filename} row {row_number}: too few columns"
                        )
                    clean_row = {
                        str(key): str(value) for key, value in row.items()
                    }
                    clean_row["__row_number__"] = str(row_number)
                    rows.append(clean_row)
        except FileNotFoundError as error:
            raise MarketDataUnavailableError(
                f"required CSV file does not exist: {path}"
            ) from error
        return rows

    def _observation(
        self, row: Mapping[str, str], filename: str, value_field: str
    ) -> MarketObservation[float]:
        try:
            retrieved_at_text = row["retrieved_at"].strip()
            return MarketObservation(
                value=self._required_float(row, filename, value_field),
                timestamp=self._timestamp(row, filename, "timestamp"),
                source=row["source"],
                field=value_field,
                dataset=row["dataset"] or None,
                retrieved_at=(
                    self._parse_datetime(
                        retrieved_at_text, filename, row, "retrieved_at"
                    )
                    if retrieved_at_text
                    else None
                ),
            )
        except MarketDataValidationError as error:
            raise self._malformed(filename, row, str(error)) from error

    def _timestamp(
        self, row: Mapping[str, str], filename: str, field: str
    ) -> datetime:
        return self._parse_datetime(row[field], filename, row, field)

    def _parse_datetime(
        self,
        value: str,
        filename: str,
        row: Mapping[str, str],
        field: str,
    ) -> datetime:
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except (AttributeError, ValueError) as error:
            raise self._malformed(
                filename, row, f"{field} must be an ISO-8601 datetime"
            ) from error
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise self._malformed(filename, row, f"{field} must be timezone-aware")
        return parsed

    def _required_float(
        self, row: Mapping[str, str], filename: str, field: str
    ) -> float:
        value = self._optional_float(row, filename, field)
        if value is None:
            raise self._malformed(filename, row, f"{field} must not be empty")
        return value

    def _optional_float(
        self, row: Mapping[str, str], filename: str, field: str
    ) -> float | None:
        text = row[field].strip()
        if not text:
            return None
        try:
            value = float(text)
        except ValueError as error:
            raise self._malformed(filename, row, f"{field} must be a number") from error
        if not isfinite(value):
            raise self._malformed(filename, row, f"{field} must be finite")
        return value

    @staticmethod
    def _require_aware(value: datetime, field: str) -> None:
        if not isinstance(value, datetime):
            raise TypeError(f"{field} must be a datetime")
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"{field} must be timezone-aware")

    @staticmethod
    def _malformed(
        filename: str, row: Mapping[str, str], detail: str
    ) -> MalformedMarketDataError:
        row_number = row.get("__row_number__", "?")
        return MalformedMarketDataError(f"{filename} row {row_number}: {detail}")
