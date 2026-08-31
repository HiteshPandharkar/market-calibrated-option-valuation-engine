"""Rate conventions shared by market-input curves."""

from enum import Enum


class CompoundingConvention(str, Enum):
    """Supported interest-rate compounding conventions."""

    CONTINUOUS = "CONTINUOUS"


class DayCountConvention(str, Enum):
    """Supported conversions from calendar time to year fractions."""

    ACTUAL_365_FIXED = "ACTUAL_365_FIXED"


class InterpolationMethod(str, Enum):
    """Supported methods for values between yield-curve pillars."""

    LINEAR_ZERO_RATE = "LINEAR_ZERO_RATE"
