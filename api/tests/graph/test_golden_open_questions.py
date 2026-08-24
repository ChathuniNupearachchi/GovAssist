"""Golden open-question scenarios, run for real against the agent — no
mocking, matching this project's convention for evaluative tests. See
golden_open_questions.py for the scenarios and why each was chosen to
discriminate.

This is the per-commit regression gate — one pass per scenario. For the
tracked, repeated-run stability metric (the 8/7/7/8/9-style range),
see `measure_open_question_stability.py`.
"""

from __future__ import annotations

import pytest

from app.chat.agent import answer_with_agent

from .golden_open_question_eval import evaluate_scenario
from .golden_open_questions import SCENARIOS

pytestmark = pytest.mark.real_api


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s["name"] for s in SCENARIOS])
def test_golden_open_question(db, scenario):
    result = answer_with_agent(db, scenario["query"])
    reason = evaluate_scenario(result, scenario)
    if reason == "skipped":
        return  # genuinely ambiguous scenario — reported, not asserted
    assert reason is None, f"{scenario['name']}: {reason}"
