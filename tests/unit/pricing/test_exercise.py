from datetime import date

from pyoptionpricer import BermudanExercise, ExerciseStyle
from pyoptionpricer.pricing.exercise import (
    BermudanExercisePolicy,
    exercise_policy,
    map_bermudan_exercise_steps,
)


def test_bermudan_policy_exercises_only_at_eligible_steps() -> None:
    policy = BermudanExercisePolicy(frozenset({2}))

    assert policy.node_value(5.0, 10.0, 1) == (5.0, False)
    assert policy.node_value(5.0, 10.0, 2) == (10.0, True)


def test_mapping_ignores_lapsed_dates_and_maps_valuation_and_expiry() -> None:
    schedule = BermudanExercise(
        (date(2026, 6, 1), date(2026, 9, 1), date(2027, 9, 1))
    )

    mapped = map_bermudan_exercise_steps(
        schedule,
        valuation_date=date(2026, 9, 1),
        expiry=date(2027, 9, 1),
        steps=365,
    )

    assert mapped == frozenset({0, 365})


def test_existing_exercise_policy_call_contract_is_preserved() -> None:
    assert exercise_policy(ExerciseStyle.EUROPEAN).node_value(5.0, 10.0) == (
        5.0,
        False,
    )
    assert exercise_policy(ExerciseStyle.AMERICAN).node_value(5.0, 10.0) == (
        10.0,
        True,
    )
