"""Shared pass/fail evaluation for one open-question golden scenario's
result — used by both `test_golden_open_questions.py` (the per-commit
regression gate) and `measure_open_question_stability.py` (the tracked,
repeated-run metric), so the two never drift out of agreement on what
"pass" means.
"""

from __future__ import annotations

from app.chat.agent import AgentAnswer


def evaluate_scenario(result: AgentAnswer | None, scenario: dict) -> str | None:
    """Returns None if `result` satisfies `scenario`'s expectations, a
    human-readable failure reason otherwise. Returns "skipped" for a
    scenario with `expect_grounded: None` (reported, not asserted —
    genuinely ambiguous, e.g. scenario #9)."""
    expect_grounded = scenario["expect_grounded"]
    if expect_grounded is None:
        return "skipped"

    if not expect_grounded:
        if result is not None:
            return f"expected a refusal, got a grounded answer: {result.text[:200]}"
        return None

    if result is None:
        return "expected a grounded answer, got a refusal"

    text_lower = result.text.lower()

    if "must_contain_any" in scenario:
        if not any(s.lower() in text_lower for s in scenario["must_contain_any"]):
            return f"missing one of {scenario['must_contain_any']} in the answer"

    if "must_also_contain_any" in scenario:
        if not any(s.lower() in text_lower for s in scenario["must_also_contain_any"]):
            return f"missing one of {scenario['must_also_contain_any']} in the answer"

    if "min_tool_calls" in scenario:
        if len(result.trace) < scenario["min_tool_calls"]:
            return f"expected at least {scenario['min_tool_calls']} tool calls, got {len(result.trace)}"

    return None
