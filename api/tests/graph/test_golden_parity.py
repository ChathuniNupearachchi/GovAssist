"""Task 1.8 — golden-parity: the graph must reproduce the pre-graph
system's output for every golden scenario (graph-orchestration spec's
"the graph reproduces the pre-graph flow's behavior end to end").

Two angles, since the ten `GOLDEN_SCENARIOS` are answer dicts (used to
test `resolve_case` directly), not citizen message sequences:

1. `resolve` path — every golden scenario's answers, seeded as
   `CaseAnswer` rows, resolved via `run_resolve_action` (the graph) and
   compared against `resolve_case` called directly (the same function
   `test_golden.py` already exhaustively verifies against hand-checked
   expected output) — a real per-scenario parity check.
2. `message` path — one full renewal conversation (scenario 1's answer
   sequence, as real chat messages) driven through both the pre-graph
   `router.handle_message` and the graph's `run_message_turn` on two
   separately seeded cases, then resolved directly and compared — proves
   the classify/record_facts/next_question/agent-cycle path converges to
   the same recorded facts and resolved plan as the pre-graph router.

Per the request: any scenario whose graph output differs from the
pre-graph/direct-engine output is reported via a failing assertion with
both outputs shown — nothing here silently adjusts an expected value to
match new behavior.
"""

from __future__ import annotations

import pytest

from app.chat import router as chat_router
from app.engine.renewal_intake import RENEWAL_QUESTIONS
from app.engine.resolver import resolve_case
from app.graph.build import run_message_turn, run_resolve_action
from app.models import Case, CaseAnswer, Question
from tests.engine.golden_scenarios import GOLDEN_SCENARIOS

_PROMPT_BY_ATTRIBUTE = {attribute: prompt for attribute, prompt, _, _, _ in RENEWAL_QUESTIONS}


def _seed_case_answers(db, case: Case, answers: dict[str, str | None]) -> None:
    for attribute, value in answers.items():
        if value is None:
            continue
        prompt = _PROMPT_BY_ATTRIBUTE.get(attribute)
        if prompt is None:
            continue
        question = db.query(Question).filter(
            Question.service_id == case.service_id, Question.prompt == prompt
        ).first()
        if question is None:
            continue
        db.add(CaseAnswer(case_id=case.id, question_id=question.id, value=value))
    db.commit()


@pytest.fixture()
def case(db, renewal_service_id):
    c = Case(service_id=renewal_service_id, device_ref="test-device-golden-parity")
    db.add(c)
    db.commit()
    yield c
    db.query(CaseAnswer).filter(CaseAnswer.case_id == c.id).delete()
    db.query(Case).filter(Case.id == c.id).delete()
    db.commit()


# Scenario 9 ("Applying from abroad") models `district = None` — to
# `resolve_case()` called directly with that raw dict, a `None` value
# means "known to have no district" (falls through to "list every
# Regional Office"). But the graph's `resolve` action goes through the
# real readiness gate (`next_question`, reading actual `CASE_ANSWER`
# rows — the same gate `app/api/cases.py` and `app/chat/tools.py`'s
# `resolve_case` tool already enforce today), which has no way to
# represent "district explicitly unknown" as a seeded answer — only "no
# row exists", i.e. not yet answered. So the real, gated path can never
# actually reach `resolve_case` with district unanswered; scenario 9 as
# modeled only exercises the pure function directly, not the gated path
# this parity test is checking. Confirmed (see PR discussion): the other
# 9/10 scenarios and the full message-path conversation test match
# exactly — this exclusion is about what this test can compare, not a
# graph behavior difference.
_SCENARIOS_REACHABLE_THROUGH_THE_READINESS_GATE = [
    s for s in GOLDEN_SCENARIOS if s["name"] != "9. Applying from abroad"
]


@pytest.mark.parametrize(
    "scenario",
    _SCENARIOS_REACHABLE_THROUGH_THE_READINESS_GATE,
    ids=[s["name"] for s in _SCENARIOS_REACHABLE_THROUGH_THE_READINESS_GATE],
)
def test_resolve_action_matches_direct_engine_for_every_golden_scenario(db, case, scenario):
    _seed_case_answers(db, case, scenario["answers"])

    graph_result = run_resolve_action(db, case.id)
    direct_result = resolve_case(db, scenario["answers"])

    assert graph_result["ready"] is True, (
        f"{scenario['name']}: graph resolve was not ready — {graph_result}"
    )

    if scenario["expect_scope_gate"]:
        assert direct_result.scope_gate is not None
        assert graph_result.get("scope_gate") == direct_result.scope_gate.reason, (
            f"{scenario['name']}: graph scope_gate={graph_result.get('scope_gate')!r} "
            f"vs direct scope_gate={direct_result.scope_gate.reason!r}"
        )
        return

    assert direct_result.scope_gate is None
    assert "scope_gate" not in graph_result or graph_result.get("scope_gate") is None

    graph_labels = {r["label"] for r in graph_result["requirements"]}
    direct_labels = {r.label for r in direct_result.requirements}
    assert graph_labels == direct_labels, (
        f"{scenario['name']}: requirement labels differ.\n"
        f"  graph:  {sorted(graph_labels)}\n"
        f"  direct: {sorted(direct_labels)}"
    )

    assert graph_result["fee"]["base_amount"] == direct_result.fee.base_amount, (
        f"{scenario['name']}: fee differs — graph={graph_result['fee']['base_amount']} "
        f"vs direct={direct_result.fee.base_amount}"
    )

    graph_offices = {o["name"] for o in (graph_result["offices"] or {}).get("offices", [])}
    direct_offices = {o.name for o in direct_result.offices.offices} if direct_result.offices else set()
    assert graph_offices == direct_offices, (
        f"{scenario['name']}: offices differ.\n"
        f"  graph:  {sorted(graph_offices)}\n"
        f"  direct: {sorted(direct_offices)}"
    )


# A straightforward renewal's answer sequence as real chat messages,
# following RENEWAL_QUESTIONS' actual order (age, holds_passport,
# name_changed, dual_citizen, [section_19_2 skipped — only relevant once
# dual_citizen=true], profession, buddhist_priest, district,
# service_basis) — every token matches try_deterministic_match's
# lexicon (see test_integration.py's precedent, and note "Teacher" not
# "" for profession: the deterministic matcher only accepts a
# *non-empty* free-text profession, so an empty answer would fall
# through to a live classifier call and make this test's determinism
# depend on model judgment it doesn't need to).
_MESSAGE_SEQUENCE = ["30", "yes", "no", "no", "Teacher", "no", "Colombo", "normal"]


@pytest.fixture()
def router_case(db, renewal_service_id):
    c = Case(service_id=renewal_service_id, device_ref="test-device-parity-router")
    db.add(c)
    db.commit()
    yield c
    db.query(CaseAnswer).filter(CaseAnswer.case_id == c.id).delete()
    db.query(Case).filter(Case.id == c.id).delete()
    db.commit()


@pytest.fixture()
def graph_case(db, renewal_service_id):
    c = Case(service_id=renewal_service_id, device_ref="test-device-parity-graph")
    db.add(c)
    db.commit()
    yield c
    db.query(CaseAnswer).filter(CaseAnswer.case_id == c.id).delete()
    db.query(Case).filter(Case.id == c.id).delete()
    db.commit()


def _recorded_answers(db, case_id) -> dict[str, str]:
    rows = (
        db.query(CaseAnswer.value, Question.prompt)
        .join(Question, CaseAnswer.question_id == Question.id)
        .filter(CaseAnswer.case_id == case_id)
        .all()
    )
    prompt_to_attribute = {prompt: attribute for attribute, prompt, _, _, _ in RENEWAL_QUESTIONS}
    return {prompt_to_attribute[prompt]: value for value, prompt in rows if prompt in prompt_to_attribute}


@pytest.mark.real_api
def test_full_renewal_conversation_matches_router_output(db, router_case, graph_case):
    for message in _MESSAGE_SEQUENCE:
        chat_router.handle_message(db, router_case, message)
        db.commit()

    for message in _MESSAGE_SEQUENCE:
        run_message_turn(db, graph_case, message)
        db.commit()

    router_answers = _recorded_answers(db, router_case.id)
    graph_answers = _recorded_answers(db, graph_case.id)
    assert graph_answers == router_answers, (
        f"Recorded answers differ.\n  router: {router_answers}\n  graph:  {graph_answers}"
    )

    router_resolution = resolve_case(db, router_answers)
    graph_resolution = resolve_case(db, graph_answers)

    router_labels = {r.label for r in router_resolution.requirements}
    graph_labels = {r.label for r in graph_resolution.requirements}
    assert graph_labels == router_labels, (
        f"Resolved requirement labels differ.\n"
        f"  router: {sorted(router_labels)}\n  graph:  {sorted(graph_labels)}"
    )
    assert graph_resolution.fee.base_amount == router_resolution.fee.base_amount
