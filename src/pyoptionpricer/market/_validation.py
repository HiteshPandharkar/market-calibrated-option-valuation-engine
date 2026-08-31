"""Shared validation helpers for market-domain boundaries."""

from datetime import datetime
from math import isfinite
from numbers import Real
from typing import TypeVar

from pyoptionpricer.market.exceptions import MarketDataValidationError

ValidationError = TypeVar("ValidationError", bound=MarketDataValidationError)


def require_aware_datetime(
    value: datetime,
    field_name: str,
    error_type: type[ValidationError],
) -> None:
    """Require a datetime whose UTC offset is defined."""
    if not isinstance(value, datetime):
        raise error_type(f"{field_name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise error_type(f"{field_name} must be timezone-aware")


def require_non_empty_text(
    value: str,
    field_name: str,
    error_type: type[ValidationError],
) -> None:
    """Require non-blank textual metadata."""
    if not isinstance(value, str) or not value.strip():
        raise error_type(f"{field_name} must be a non-empty string")


def require_finite_number(
    value: object,
    field_name: str,
    error_type: type[ValidationError],
) -> None:
    """Require a real, finite numeric value while excluding booleans."""
    if isinstance(value, bool) or not isinstance(value, Real):
        raise error_type(f"{field_name} must be a real number")
    if not isfinite(float(value)):
        raise error_type(f"{field_name} must be finite")
