"""Product-specific analytical strategies for Black-Scholes-Merton pricing."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from math import erfc, exp, isfinite, log, pi, sqrt
from types import MappingProxyType
from typing import ClassVar, Final, Protocol

from pyoptionpricer.domain import (
    CashOrNothingPayoff,
    OptionProduct,
    OptionType,
    TerminalPayoff,
    VanillaPayoff,
)
from pyoptionpricer.models import BSMModelParameters
from pyoptionpricer.pricing.errors import PricingError
from pyoptionpricer.pricing.greeks import OptionGreeks
from pyoptionpricer.pricing.results import BSMPricingDiagnostics


@dataclass(frozen=True, slots=True)
class BSMInputs:
    """Validated common numerical inputs shared by BSM product strategies."""

    spot: float
    strike: float
    maturity: float
    rate: float
    dividend: float
    volatility: float
    spot_discount_factor: float = field(init=False)
    strike_discount_factor: float = field(init=False)

    def __post_init__(self) -> None:
        values = (
            self.spot,
            self.strike,
            self.maturity,
            self.rate,
            self.dividend,
            self.volatility,
        )
        if any(not isfinite(value) for value in values):
            raise PricingError("BSM inputs must be finite")
        if self.spot <= 0:
            raise PricingError("BSM spot must be positive")
        if self.strike <= 0:
            raise PricingError("BSM strike must be positive")
        if self.maturity < 0:
            raise PricingError("BSM time to expiry must be non-negative")
        if self.volatility < 0:
            raise PricingError("BSM volatility must be non-negative")
        object.__setattr__(
            self,
            "spot_discount_factor",
            _discount_factor(self.dividend, self.maturity, "dividend yield"),
        )
        object.__setattr__(
            self,
            "strike_discount_factor",
            _discount_factor(self.rate, self.maturity, "risk-free rate"),
        )


@dataclass(frozen=True, slots=True)
class BSMCalculation:
    """Product-strategy output consumed by the model-level engine."""

    price: float
    greeks: OptionGreeks
    diagnostics: BSMPricingDiagnostics


class BSMProductPricer(Protocol):
    """Narrow extension contract for one BSM-supported option product."""

    product: OptionProduct

    def price(
        self,
        inputs: BSMInputs,
        payoff: TerminalPayoff,
        parameters: BSMModelParameters,
    ) -> BSMCalculation: ...


@dataclass(frozen=True, slots=True)
class VanillaBSMProductPricer:
    """Analytical and deterministic-limit valuation for vanilla payoffs."""

    product: ClassVar[OptionProduct] = OptionProduct.VANILLA

    def price(
        self,
        inputs: BSMInputs,
        payoff: TerminalPayoff,
        parameters: BSMModelParameters,
    ) -> BSMCalculation:
        if not isinstance(payoff, VanillaPayoff):
            raise PricingError("vanilla contract requires a vanilla payoff")
        if _uses_deterministic_limit(inputs, parameters):
            price, greeks = self._deterministic_limit(inputs, payoff.option_type)
            return _deterministic_calculation(inputs, price, greeks)

        d1, d2 = _standardized_moneyness(inputs)
        n_d1 = _normal_cdf(d1)
        n_d2 = _normal_cdf(d2)
        root_maturity = sqrt(inputs.maturity)
        standard_deviation = inputs.volatility * root_maturity
        density = exp(-0.5 * d1 * d1) / sqrt(2.0 * pi)
        discounted_spot = inputs.spot * inputs.spot_discount_factor
        discounted_strike = inputs.strike * inputs.strike_discount_factor
        gamma = (
            inputs.spot_discount_factor
            * density
            / (inputs.spot * standard_deviation)
        )
        vega = discounted_spot * density * root_maturity
        common_theta = (
            -discounted_spot
            * density
            * inputs.volatility
            / (2.0 * root_maturity)
        )

        if payoff.option_type is OptionType.CALL:
            price = discounted_spot * n_d1 - discounted_strike * n_d2
            delta = inputs.spot_discount_factor * n_d1
            theta = (
                common_theta
                - inputs.rate * discounted_strike * n_d2
                + inputs.dividend * discounted_spot * n_d1
            )
            rho = (
                inputs.strike
                * inputs.maturity
                * inputs.strike_discount_factor
                * n_d2
            )
        else:
            n_minus_d1 = _normal_cdf(-d1)
            n_minus_d2 = _normal_cdf(-d2)
            price = discounted_strike * n_minus_d2 - discounted_spot * n_minus_d1
            delta = -inputs.spot_discount_factor * n_minus_d1
            theta = (
                common_theta
                + inputs.rate * discounted_strike * n_minus_d2
                - inputs.dividend * discounted_spot * n_minus_d1
            )
            rho = (
                -inputs.strike
                * inputs.maturity
                * inputs.strike_discount_factor
                * n_minus_d2
            )
        return _analytical_calculation(
            inputs,
            price,
            OptionGreeks(delta, gamma, theta, vega, rho),
            d1,
            d2,
        )

    @staticmethod
    def _deterministic_limit(
        inputs: BSMInputs, option_type: OptionType
    ) -> tuple[float, OptionGreeks]:
        discounted_spot = inputs.spot * inputs.spot_discount_factor
        discounted_strike = inputs.strike * inputs.strike_discount_factor
        forward_intrinsic = discounted_spot - discounted_strike
        if forward_intrinsic > 0:
            call_weight = 1.0
        elif forward_intrinsic < 0:
            call_weight = 0.0
        else:
            call_weight = 0.5

        if option_type is OptionType.CALL:
            weight = call_weight
            price = max(forward_intrinsic, 0.0)
            delta = weight * inputs.spot_discount_factor
            theta = weight * (
                inputs.dividend * discounted_spot
                - inputs.rate * discounted_strike
            )
            rho = (
                weight
                * inputs.strike
                * inputs.maturity
                * inputs.strike_discount_factor
            )
        else:
            weight = 1.0 - call_weight
            price = max(-forward_intrinsic, 0.0)
            delta = -weight * inputs.spot_discount_factor
            theta = weight * (
                inputs.rate * discounted_strike
                - inputs.dividend * discounted_spot
            )
            rho = (
                -weight
                * inputs.strike
                * inputs.maturity
                * inputs.strike_discount_factor
            )
        return price, OptionGreeks(delta, 0.0, theta, 0.0, rho)


@dataclass(frozen=True, slots=True)
class CashDigitalBSMProductPricer:
    """Analytical and deterministic-limit valuation for cash digitals."""

    product: ClassVar[OptionProduct] = OptionProduct.DIGITAL

    def price(
        self,
        inputs: BSMInputs,
        payoff: TerminalPayoff,
        parameters: BSMModelParameters,
    ) -> BSMCalculation:
        if not isinstance(payoff, CashOrNothingPayoff):
            raise PricingError("digital contract requires a cash-or-nothing payoff")
        if _uses_deterministic_limit(inputs, parameters):
            price, greeks = self._deterministic_limit(inputs, payoff)
            return _deterministic_calculation(inputs, price, greeks)

        d1, d2 = _standardized_moneyness(inputs)
        root_maturity = sqrt(inputs.maturity)
        standard_deviation = inputs.volatility * root_maturity
        density = exp(-0.5 * d2 * d2) / sqrt(2.0 * pi)
        discounted_payout = payoff.payout * inputs.strike_discount_factor
        delta_magnitude = discounted_payout * density / (
            inputs.spot * standard_deviation
        )
        gamma_magnitude = -discounted_payout * density * d1 / (
            inputs.spot**2 * standard_deviation**2
        )
        vega_magnitude = -discounted_payout * density * d1 / inputs.volatility
        d2_time_derivative = (
            (inputs.rate - inputs.dividend - 0.5 * inputs.volatility**2)
            * inputs.maturity
            - log(inputs.spot / inputs.strike)
        ) / (2.0 * inputs.volatility * inputs.maturity**1.5)

        if payoff.option_type is OptionType.CALL:
            probability = _normal_cdf(d2)
            price = discounted_payout * probability
            delta = delta_magnitude
            gamma = gamma_magnitude
            theta = discounted_payout * (
                inputs.rate * probability - density * d2_time_derivative
            )
            vega = vega_magnitude
            rho = discounted_payout * (
                -inputs.maturity * probability
                + density * root_maturity / inputs.volatility
            )
        else:
            probability = _normal_cdf(-d2)
            price = discounted_payout * probability
            delta = -delta_magnitude
            gamma = -gamma_magnitude
            theta = discounted_payout * (
                inputs.rate * probability + density * d2_time_derivative
            )
            vega = -vega_magnitude
            rho = discounted_payout * (
                -inputs.maturity * probability
                - density * root_maturity / inputs.volatility
            )
        return _analytical_calculation(
            inputs,
            price,
            OptionGreeks(delta, gamma, theta, vega, rho),
            d1,
            d2,
        )

    @staticmethod
    def _deterministic_limit(
        inputs: BSMInputs, payoff: CashOrNothingPayoff
    ) -> tuple[float, OptionGreeks]:
        discounted_spot = inputs.spot * inputs.spot_discount_factor
        discounted_strike = inputs.strike * inputs.strike_discount_factor
        is_in_the_money = (
            discounted_spot > discounted_strike
            if payoff.option_type is OptionType.CALL
            else discounted_spot < discounted_strike
        )
        if not is_in_the_money:
            return 0.0, OptionGreeks(0.0, 0.0, 0.0, 0.0, 0.0)
        price = payoff.payout * inputs.strike_discount_factor
        return price, OptionGreeks(
            delta=0.0,
            gamma=0.0,
            theta=inputs.rate * price,
            vega=0.0,
            rho=-inputs.maturity * price,
        )


def _uses_deterministic_limit(
    inputs: BSMInputs, parameters: BSMModelParameters
) -> bool:
    return (
        inputs.maturity <= parameters.near_zero_maturity
        or inputs.volatility <= parameters.near_zero_volatility
    )


def _discount_factor(rate: float, maturity: float, name: str) -> float:
    try:
        factor = exp(-rate * maturity)
    except OverflowError as error:
        raise PricingError(
            f"{name} is outside the numerically supported range"
        ) from error
    if not isfinite(factor):
        raise PricingError(f"{name} produced an invalid discount factor")
    return factor


def _standardized_moneyness(inputs: BSMInputs) -> tuple[float, float]:
    standard_deviation = inputs.volatility * sqrt(inputs.maturity)
    try:
        d1 = (
            log(inputs.spot / inputs.strike)
            + (
                inputs.rate
                - inputs.dividend
                + 0.5 * inputs.volatility**2
            )
            * inputs.maturity
        ) / standard_deviation
    except (OverflowError, ZeroDivisionError) as error:
        raise PricingError("BSM standardized moneyness is not computable") from error
    d2 = d1 - standard_deviation
    if not isfinite(d1) or not isfinite(d2):
        raise PricingError("BSM standardized moneyness must be finite")
    return d1, d2


def _normal_cdf(value: float) -> float:
    return 0.5 * erfc(-value / sqrt(2.0))


def _analytical_calculation(
    inputs: BSMInputs,
    price: float,
    greeks: OptionGreeks,
    d1: float,
    d2: float,
) -> BSMCalculation:
    return BSMCalculation(
        price,
        greeks,
        BSMPricingDiagnostics(
            "ANALYTICAL",
            inputs.spot_discount_factor,
            inputs.strike_discount_factor,
            d1,
            d2,
        ),
    )


def _deterministic_calculation(
    inputs: BSMInputs, price: float, greeks: OptionGreeks
) -> BSMCalculation:
    return BSMCalculation(
        price,
        greeks,
        BSMPricingDiagnostics(
            "DETERMINISTIC_LIMIT",
            inputs.spot_discount_factor,
            inputs.strike_discount_factor,
            None,
            None,
        ),
    )


BSM_PRODUCT_PRICERS: Final[Mapping[OptionProduct, BSMProductPricer]] = (
    MappingProxyType(
        {
            OptionProduct.VANILLA: VanillaBSMProductPricer(),
            OptionProduct.DIGITAL: CashDigitalBSMProductPricer(),
        }
    )
)
