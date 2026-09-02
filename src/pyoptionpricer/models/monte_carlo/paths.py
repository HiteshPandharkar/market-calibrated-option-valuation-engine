"""Reusable stochastic path generation."""

from collections.abc import Iterator
from dataclasses import dataclass
from math import isfinite

from pyoptionpricer.models.monte_carlo.processes import GeometricBrownianMotion
from pyoptionpricer.models.monte_carlo.random_numbers import RandomNumberGenerator


@dataclass(frozen=True, slots=True)
class GeneratedPath:
    """One simulated price path, including its initial value."""

    values: tuple[float, ...]
    time_step: float

    @property
    def terminal_value(self) -> float:
        return self.values[-1]


class PathGenerator:
    """Generate exact-transition GBM paths without retaining the full sample."""

    def __init__(
        self,
        process: GeometricBrownianMotion,
        random_number_generator: RandomNumberGenerator,
    ) -> None:
        if not isinstance(process, GeometricBrownianMotion):
            raise TypeError("process must be GeometricBrownianMotion")
        if not isinstance(random_number_generator, RandomNumberGenerator):
            raise TypeError(
                "random_number_generator must implement RandomNumberGenerator"
            )
        self._process = process
        self._random = random_number_generator

    def generate(
        self,
        *,
        initial_spot: float,
        maturity: float,
        time_steps: int,
        number_of_paths: int,
        antithetic_variates: bool = False,
    ) -> Iterator[GeneratedPath]:
        if not isfinite(initial_spot) or initial_spot <= 0:
            raise ValueError("initial_spot must be finite and positive")
        if not isfinite(maturity) or maturity <= 0:
            raise ValueError("maturity must be finite and positive")
        for name, value in (
            ("time_steps", time_steps),
            ("number_of_paths", number_of_paths),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if not isinstance(antithetic_variates, bool):
            raise TypeError("antithetic_variates must be a bool")
        if antithetic_variates and number_of_paths % 2:
            raise ValueError(
                "number_of_paths must be even when antithetic variates are enabled"
            )

        time_step = maturity / time_steps
        samples = number_of_paths // 2 if antithetic_variates else number_of_paths
        for _ in range(samples):
            normals = self._random.standard_normals(time_steps)
            yield self._build_path(initial_spot, time_step, normals)
            if antithetic_variates:
                yield self._build_path(
                    initial_spot, time_step, tuple(-value for value in normals)
                )

    def _build_path(
        self, initial_spot: float, time_step: float, normals: tuple[float, ...]
    ) -> GeneratedPath:
        values = [initial_spot]
        spot = initial_spot
        for normal in normals:
            spot = self._process.evolve(spot, time_step, normal)
            values.append(spot)
        return GeneratedPath(tuple(values), time_step)
