from math import exp
from statistics import fmean, variance

import pytest

from pyoptionpricer.models.monte_carlo import (
    GeometricBrownianMotion,
    PathGenerator,
    PythonRandomNumberGenerator,
)


def generator(seed: int = 7) -> PathGenerator:
    return PathGenerator(
        GeometricBrownianMotion(0.05, 0.02, 0.20),
        PythonRandomNumberGenerator(seed),
    )


def test_gbm_path_has_initial_value_requested_steps_and_exact_transition() -> None:
    process = GeometricBrownianMotion(0.05, 0.02, 0.20)
    path = next(
        PathGenerator(process, PythonRandomNumberGenerator(19)).generate(
            initial_spot=100.0,
            maturity=1.0,
            time_steps=1,
            number_of_paths=2,
            antithetic_variates=True,
        )
    )
    normal = PythonRandomNumberGenerator(19).standard_normals(1)[0]

    assert path.values == pytest.approx(
        (100.0, process.evolve(100.0, 1.0, normal)), abs=1e-14
    )
    assert path.time_step == 1.0


def test_seeded_path_generation_is_reproducible() -> None:
    settings = dict(
        initial_spot=100.0,
        maturity=0.5,
        time_steps=4,
        number_of_paths=6,
        antithetic_variates=True,
    )

    first = tuple(generator().generate(**settings))
    second = tuple(generator().generate(**settings))

    assert first == second


def test_antithetic_paths_use_opposite_normal_shocks() -> None:
    first, opposite = tuple(
        generator().generate(
            initial_spot=100.0,
            maturity=1.0,
            time_steps=3,
            number_of_paths=2,
            antithetic_variates=True,
        )
    )
    deterministic_product = 100.0**2 * exp(
        2.0 * (0.05 - 0.02 - 0.5 * 0.20**2)
    )

    assert first.terminal_value * opposite.terminal_value == pytest.approx(
        deterministic_product, rel=1e-14
    )


def test_gbm_terminal_distribution_has_risk_neutral_moments() -> None:
    terminals = [
        path.terminal_value
        for path in generator(314159).generate(
            initial_spot=100.0,
            maturity=1.0,
            time_steps=8,
            number_of_paths=20_000,
            antithetic_variates=True,
        )
    ]
    expected_mean = 100.0 * exp(0.03)
    expected_variance = (
        100.0**2 * exp(2.0 * 0.03) * (exp(0.20**2) - 1.0)
    )

    assert fmean(terminals) == pytest.approx(expected_mean, rel=0.003)
    assert variance(terminals) == pytest.approx(expected_variance, rel=0.04)
