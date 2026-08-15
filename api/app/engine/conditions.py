"""4.1 Condition evaluator.

Evaluates one Condition against a case's answers. Operators are
restricted to equals/lessThan/in (Phase 2 schema; no nesting, no AND/OR
beyond what REQUIREMENT_CONDITION's flat linkage already expresses).

Answers are a plain dict keyed by `Condition.attribute` (e.g. "age",
"dual_citizen"), not by question_id — see design.md's refinement of the
original "looks up via question_id" note: `attribute` is what both the
engine and the golden test fixtures key against, since question_id is an
opaque, seed-time-generated UUID that a hand-written test fixture can't
reasonably reference. `Condition.question_id` remains the FK of record
for DB joins and traceability; it isn't used as the runtime lookup key.
"""

from __future__ import annotations

from app.models import Condition


def evaluate_condition(condition: Condition, answers: dict[str, str]) -> bool | None:
    """Evaluate a single condition's own truth value.

    Returns True/False, or None when the case has no recorded answer for
    this condition's attribute — "missing" is distinct from "false" so
    callers can decide how to treat it (see `condition_link_passes`).
    """
    if condition.attribute not in answers:
        return None
    value = answers[condition.attribute]

    if condition.operator == "equals":
        return str(value) == condition.value

    if condition.operator == "lessThan":
        try:
            return float(value) < float(condition.value)
        except (TypeError, ValueError):
            return False

    if condition.operator == "in":
        allowed = [item.strip() for item in condition.value.split(",")]
        return str(value) in allowed

    raise ValueError(f"Unsupported condition operator: {condition.operator!r}")


def condition_link_passes(
    condition: Condition, negated: bool, answers: dict[str, str]
) -> bool:
    """The final gating result for one REQUIREMENT_CONDITION link.

    A missing answer is always not-satisfied, regardless of `negated` —
    an unanswered question must never be treated as satisfying a negated
    condition (e.g. an unanswered `dual_citizen` must not make the
    negated "NOT dual citizen" standard-set link pass prematurely).
    """
    raw = evaluate_condition(condition, answers)
    if raw is None:
        return False
    return (not raw) if negated else raw
