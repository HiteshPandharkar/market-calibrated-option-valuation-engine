"""Barrier-state valuation isolated from the generic CRR lattice engine."""

from dataclasses import dataclass
from math import isclose, log

from pyoptionpricer.domain import (
    BarrierDirection,
    BarrierKnockType,
    BarrierOptionContract,
)
from pyoptionpricer.models.tree.parameters import CRRTreeParameters


@dataclass(frozen=True, slots=True)
class BarrierLatticeValues:
    """Root and early-level values needed for price and tree Greeks."""

    root: float
    first_level: tuple[float, float]
    second_level: tuple[float, float, float]


class BarrierLatticePricer:
    """Value discrete-node barriers while carrying inactive/active state."""

    def price(
        self,
        contract: BarrierOptionContract,
        spot: float,
        tree: CRRTreeParameters,
        steps: int,
    ) -> BarrierLatticeValues:
        payoff = contract.payoff
        active_values = [
            payoff.value_at(self._node_spot(spot, tree, steps, up_moves))
            for up_moves in range(steps + 1)
        ]
        inactive_values = [
            self._terminal_inactive_value(
                contract,
                self._node_spot(spot, tree, steps, up_moves),
                active_values[up_moves],
            )
            for up_moves in range(steps + 1)
        ]

        first_level: tuple[float, float] | None = None
        second_level: tuple[float, float, float] | None = None
        first_active: tuple[float, float] | None = None
        second_active: tuple[float, float, float] | None = None
        probability = tree.risk_neutral_probability
        for time_index in range(steps - 1, -1, -1):
            next_active: list[float] = []
            next_inactive: list[float] = []
            for up_moves in range(time_index + 1):
                active = self._discounted_continuation(
                    active_values, up_moves, probability, tree.discount_factor
                )
                inactive = self._discounted_continuation(
                    inactive_values, up_moves, probability, tree.discount_factor
                )
                node_spot = self._node_spot(
                    spot, tree, time_index, up_moves
                )
                next_active.append(active)
                next_inactive.append(
                    self._inactive_node_value(contract, node_spot, active, inactive)
                )
            active_values = next_active
            inactive_values = next_inactive
            selected = inactive_values
            if time_index == 2:
                second_level = (selected[0], selected[1], selected[2])
                second_active = (
                    active_values[0],
                    active_values[1],
                    active_values[2],
                )
            elif time_index == 1:
                first_level = (selected[0], selected[1])
                first_active = (active_values[0], active_values[1])

        if (
            first_level is None
            or second_level is None
            or first_active is None
            or second_active is None
        ):
            raise ValueError("barrier lattice requires at least two steps")
        if self._is_breached(contract, spot):
            if contract.knock_type is BarrierKnockType.IN:
                return BarrierLatticeValues(
                    active_values[0], first_active, second_active
                )
            return BarrierLatticeValues(
                contract.rebate,
                (contract.rebate, contract.rebate),
                (contract.rebate, contract.rebate, contract.rebate),
            )
        return BarrierLatticeValues(inactive_values[0], first_level, second_level)

    @classmethod
    def _terminal_inactive_value(
        cls,
        contract: BarrierOptionContract,
        node_spot: float,
        active_value: float,
    ) -> float:
        if cls._is_breached(contract, node_spot):
            if contract.knock_type is BarrierKnockType.OUT:
                return contract.rebate
            return active_value
        if contract.knock_type is BarrierKnockType.OUT:
            return active_value
        return contract.rebate

    @classmethod
    def _inactive_node_value(
        cls,
        contract: BarrierOptionContract,
        node_spot: float,
        active_value: float,
        inactive_continuation: float,
    ) -> float:
        if not cls._is_breached(contract, node_spot):
            return inactive_continuation
        if contract.knock_type is BarrierKnockType.OUT:
            return contract.rebate
        return active_value

    @staticmethod
    def _discounted_continuation(
        values: list[float],
        up_moves: int,
        probability: float,
        discount_factor: float,
    ) -> float:
        return discount_factor * (
            probability * values[up_moves + 1]
            + (1.0 - probability) * values[up_moves]
        )

    @staticmethod
    def _node_spot(
        spot: float,
        tree: CRRTreeParameters,
        time_index: int,
        up_moves: int,
    ) -> float:
        return (
            spot
            * tree.up_factor**up_moves
            * tree.down_factor ** (time_index - up_moves)
        )

    @staticmethod
    def _is_breached(contract: BarrierOptionContract, node_spot: float) -> bool:
        if contract.barrier_direction is BarrierDirection.UP:
            return node_spot >= contract.barrier_level
        return node_spot <= contract.barrier_level


def barrier_grid_warnings(
    contract: BarrierOptionContract,
    spot: float,
    tree: CRRTreeParameters,
    steps: int,
) -> tuple[str, ...]:
    """Describe material placement of the barrier relative to the CRR grid."""
    if BarrierLatticePricer._is_breached(contract, spot):
        return ()
    log_distance = (
        log(contract.barrier_level) - log(spot)
    ) / log(tree.up_factor)
    if abs(log_distance) > steps:
        return (
            "barrier is outside the terminal CRR price range and cannot be "
            "reached on the selected grid",
        )
    if not isclose(log_distance, round(log_distance), abs_tol=1e-10):
        return (
            "barrier does not align with a CRR price node; the discrete-node "
            "price may oscillate as tree steps change",
        )
    return ()
