import pytest

from pyoptionpricer.pricing.greeks import (
    GreekCalculationError,
    OptionGreeks,
    calculate_tree_greeks,
)


def test_tree_greeks_use_first_two_lattice_levels() -> None:
    greeks = calculate_tree_greeks(
        root_value=10.0,
        first_level_values=(6.0, 16.0),
        second_level_values=(3.0, 9.0, 23.0),
        first_level_spots=(90.0, 110.0),
        second_level_spots=(80.0, 100.0, 120.0),
        time_step=0.25,
    )

    assert isinstance(greeks, OptionGreeks)
    assert greeks.delta == pytest.approx(0.5)
    assert greeks.gamma == pytest.approx(0.02)
    assert greeks.theta == pytest.approx(-2.0)


@pytest.mark.parametrize(
    ("first_level_spots", "second_level_spots"),
    [
        ((100.0, 100.0), (80.0, 100.0, 120.0)),
        ((90.0, 110.0), (100.0, 100.0, 100.0)),
    ],
)
def test_tree_greeks_reject_invalid_spot_spacing(
    first_level_spots: tuple[float, float],
    second_level_spots: tuple[float, float, float],
) -> None:
    with pytest.raises(GreekCalculationError, match="spot spacing"):
        calculate_tree_greeks(
            root_value=10.0,
            first_level_values=(6.0, 16.0),
            second_level_values=(3.0, 9.0, 23.0),
            first_level_spots=first_level_spots,
            second_level_spots=second_level_spots,
            time_step=0.25,
        )


@pytest.mark.parametrize("time_step", [0.0, float("nan")])
def test_tree_greeks_reject_invalid_time_step(time_step: float) -> None:
    with pytest.raises(GreekCalculationError, match="time step"):
        calculate_tree_greeks(
            root_value=10.0,
            first_level_values=(6.0, 16.0),
            second_level_values=(3.0, 9.0, 23.0),
            first_level_spots=(90.0, 110.0),
            second_level_spots=(80.0, 100.0, 120.0),
            time_step=time_step,
        )
