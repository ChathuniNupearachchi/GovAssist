"""8.3 Condition evaluator unit tests — one per operator, plus the
missing-answer case."""

from app.engine.conditions import condition_link_passes, evaluate_condition
from app.models import Condition


def _condition(attribute: str, operator: str, value: str) -> Condition:
    # Constructed in memory, never persisted — the evaluator only reads
    # attribute/operator/value, so no DB round-trip is needed for these.
    return Condition(attribute=attribute, operator=operator, value=value)


def test_equals_operator():
    c = _condition("dual_citizen", "equals", "true")
    assert evaluate_condition(c, {"dual_citizen": "true"}) is True
    assert evaluate_condition(c, {"dual_citizen": "false"}) is False


def test_less_than_operator():
    c = _condition("age", "lessThan", "16")
    assert evaluate_condition(c, {"age": "10"}) is True
    assert evaluate_condition(c, {"age": "16"}) is False
    assert evaluate_condition(c, {"age": "40"}) is False


def test_in_operator():
    c = _condition("district", "in", "Kandy,Matara,Vavuniya,Kurunegala,Jaffna")
    assert evaluate_condition(c, {"district": "Kandy"}) is True
    assert evaluate_condition(c, {"district": "Colombo"}) is False


def test_missing_answer_evaluates_as_not_satisfied_no_error():
    c = _condition("dual_citizen", "equals", "true")
    assert evaluate_condition(c, {}) is None  # raw: "unknown", not an error
    assert condition_link_passes(c, negated=False, answers={}) is False
    assert condition_link_passes(c, negated=True, answers={}) is False  # not flipped
