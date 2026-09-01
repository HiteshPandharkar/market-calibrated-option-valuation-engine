"""First- and second-order option sensitivities."""

from dataclasses import dataclass
from math import isfinite


class GreekCalculationError(RuntimeError):
    """Raised when lattice values cannot produce numerically stable Greeks."""


@dataclass(frozen=True, slots=True)
class OptionGreeks:
    """Option sensitivities in spot and annual time units.

    ``delta`` is option-currency units per one currency unit of spot,
    ``gamma`` is the delta change per one currency unit of spot, and ``theta``
    is the option-value change per calendar year as time advances. Analytical
    engines may also supply ``vega`` and ``rho`` per unit (1.00) change in
    volatility and continuously compounded rate. Tree engines leave them
    unavailable rather than approximating them implicitly.
    """

    delta: float
    gamma: float
    theta: float
    vega: float | None = None
    rho: float | None = None

    def __post_init__(self) -> None:
        required = (self.delta, self.gamma, self.theta)
        optional = (self.vega, self.rho)
        if any(not isfinite(value) for value in required) or any(
            value is not None and not isfinite(value) for value in optional
        ):
            raise GreekCalculationError("calculated Greeks must be finite")


def calculate_tree_greeks(
    root_value: float,
    first_level_values: tuple[float, float],
    second_level_values: tuple[float, float, float],
    first_level_spots: tuple[float, float],
    second_level_spots: tuple[float, float, float],
    time_step: float,
) -> OptionGreeks:
    """Extract Delta, Gamma, and annual Theta from the first two tree levels.

    Values and spots are ordered from the all-down node to the all-up node.
    Theta uses the central node two steps forward, whose spot equals the root
    spot in a CRR tree, so its sign is the value change as calendar time passes.
    """

    if not isfinite(time_step) or time_step <= 0:
        raise GreekCalculationError("Greek time step must be finite and positive")

    down_value, up_value = first_level_values
    down_down_value, middle_value, up_up_value = second_level_values
    down_spot, up_spot = first_level_spots
    down_down_spot, middle_spot, up_up_spot = second_level_spots
    values = (
        root_value,
        down_value,
        up_value,
        down_down_value,
        middle_value,
        up_up_value,
        down_spot,
        up_spot,
        down_down_spot,
        middle_spot,
        up_up_spot,
    )
    if any(not isfinite(value) for value in values):
        raise GreekCalculationError("Greek lattice inputs must be finite")

    delta_denominator = up_spot - down_spot
    upper_delta_denominator = up_up_spot - middle_spot
    lower_delta_denominator = middle_spot - down_down_spot
    gamma_denominator = (up_up_spot - down_down_spot) / 2.0
    denominators = (
        delta_denominator,
        upper_delta_denominator,
        lower_delta_denominator,
        gamma_denominator,
    )
    if any(not isfinite(value) or value <= 0 for value in denominators):
        raise GreekCalculationError(
            "tree spot spacing is too small or invalid for stable Greeks"
        )

    delta = (up_value - down_value) / delta_denominator
    upper_delta = (up_up_value - middle_value) / upper_delta_denominator
    lower_delta = (middle_value - down_down_value) / lower_delta_denominator
    gamma = (upper_delta - lower_delta) / gamma_denominator
    theta = (middle_value - root_value) / (2.0 * time_step)
    return OptionGreeks(delta=delta, gamma=gamma, theta=theta)
