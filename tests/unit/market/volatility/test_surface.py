from datetime import UTC, date, datetime
from math import sqrt

import pytest

from pyoptionpricer.domain import OptionType
from pyoptionpricer.market import (
    MarketDataUnavailableError,
    MarketImpliedVolatilitySurface,
    MarketIVPoint,
    MarketObservation,
)


VALUATION = datetime(2026, 8, 31, 10, tzinfo=UTC)
NEAR_EXPIRY = date(2026, 9, 30)
FAR_EXPIRY = date(2026, 10, 30)


def point(expiry: date, strike: float, volatility: float) -> MarketIVPoint:
    return MarketIVPoint(
        expiry,
        strike,
        OptionType.CALL,
        MarketObservation(
            volatility,
            VALUATION,
            "NORMALIZED_VENDOR",
            "vendor_implied_volatility",
            "OPTION_CHAIN",
        ),
    )


def test_surface_selects_exact_contract_vendor_iv() -> None:
    surface = MarketImpliedVolatilitySurface(
        VALUATION, (point(NEAR_EXPIRY, 100.0, 0.20),)
    )

    selected = surface.volatility(100.0, NEAR_EXPIRY, OptionType.CALL)

    assert selected.value == pytest.approx(0.20)
    assert selected.field == "market_implied_volatility"
    assert selected.dataset == "OPTION_CHAIN"


def test_surface_interpolates_strike_linearly() -> None:
    surface = MarketImpliedVolatilitySurface(
        VALUATION,
        (
            point(NEAR_EXPIRY, 90.0, 0.24),
            point(NEAR_EXPIRY, 110.0, 0.20),
        ),
    )

    selected = surface.volatility(100.0, NEAR_EXPIRY, OptionType.CALL)

    assert selected.value == pytest.approx(0.22)


def test_surface_interpolates_expiry_in_total_variance() -> None:
    target_expiry = date(2026, 10, 15)
    surface = MarketImpliedVolatilitySurface(
        VALUATION,
        (
            point(NEAR_EXPIRY, 100.0, 0.20),
            point(FAR_EXPIRY, 100.0, 0.30),
        ),
    )

    selected = surface.volatility(100.0, target_expiry, OptionType.CALL)

    near_time = 30 / 365
    far_time = 60 / 365
    target_time = 45 / 365
    expected = sqrt(
        (0.5 * 0.20**2 * near_time + 0.5 * 0.30**2 * far_time)
        / target_time
    )
    assert selected.value == pytest.approx(expected)


def test_surface_rejects_extrapolation_when_market_iv_is_unreliable() -> None:
    surface = MarketImpliedVolatilitySurface(
        VALUATION,
        (
            point(NEAR_EXPIRY, 90.0, 0.24),
            point(NEAR_EXPIRY, 100.0, 7.0),
        ),
    )

    with pytest.raises(MarketDataUnavailableError, match="outside"):
        surface.volatility(100.0, NEAR_EXPIRY, OptionType.CALL)
