"""Random-number boundary used by stochastic simulations."""

from random import Random
from typing import Protocol, runtime_checkable


@runtime_checkable
class RandomNumberGenerator(Protocol):
    """Supply independent standard-normal variates."""

    @property
    def seed(self) -> int: ...

    def standard_normals(self, count: int) -> tuple[float, ...]: ...


class PythonRandomNumberGenerator:
    """Seeded standard-library normal generator with isolated state."""

    def __init__(self, seed: int) -> None:
        if not isinstance(seed, int) or isinstance(seed, bool):
            raise TypeError("seed must be an integer")
        self._seed = seed
        self._random = Random(seed)

    @property
    def seed(self) -> int:
        return self._seed

    def standard_normals(self, count: int) -> tuple[float, ...]:
        if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
            raise ValueError("count must be a positive integer")
        return tuple(self._random.gauss(0.0, 1.0) for _ in range(count))
