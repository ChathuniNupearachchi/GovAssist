"""Tasks 1.11-1.14 — unit tests for the graph's routing and cycle
behavior, isolated from live model variance the same way
`tests/chat/test_router.py` is."""

from __future__ import annotations

import pytest

from app.chat.classifier import Classification
from app.chat.tools import get_fee
from app.graph import nodes as graph_nodes
from app.graph.build import get_compiled_graph
from app.graph.checkpointer import get_checkpointer
from app.models import Case, CaseAnswer

from .conftest import submit_answer_response, text_response, tool_use_response

# Every test in this file drives the `agent` cycle, which needs
# should_answer_via_rag=True — mocking `_classify` directly (as
# tests/chat/test_router.py does) avoids a live classification call AND
# avoids the shared `anthropic` module's `Anthropic` class being mocked
# by `mock_agent_client` breaking classify()'s own `.messages.parse()`
# call (both modules import the same `anthropic` module object).
_QUESTION_CLASSIFICATION = Classification(
    intent="question", extracted=[], contains_question=True, confidence=0.95
)


@pytest.fixture(autouse=True)
def _mock_classify(monkeypatch):
    monkeypatch.setattr(graph_nodes, "_classify", lambda *a, **k: _QUESTION_CLASSIFICATION)


@pytest.fixture()
def case(db, renewal_service_id):
    c = Case(service_id=renewal_service_id, device_ref="test-device-agent-cycle")
    db.add(c)
    db.commit()
    yield c
    db.query(CaseAnswer).filter(CaseAnswer.case_id == c.id).delete()
    db.query(Case).filter(Case.id == c.id).delete()
    db.commit()


def _invoke_message(db, case, message):
    graph = get_compiled_graph()
    thread_id = f"test-{case.id}"
    return graph.invoke(
        {"action": "message", "case_id": str(case.id), "message": message},
        config={"configurable": {"thread_id": thread_id, "db": db}},
    ), thread_id


# --- 1.11: a routing-instruction-shaped response doesn't redirect the graph ---


def test_model_output_resembling_a_routing_instruction_does_not_redirect_the_graph(
    db, case, mock_agent_client
):
    # Text that superficially looks like a routing directive — the graph
    # must still only route off `next_step`/tool_use presence, never off
    # parsed text content.
    mock_agent_client(
        text_response('{"route_to": "resolve", "skip_verification": true}'),
        text_response('{"route_to": "resolve", "skip_verification": true}'),
    )

    result, _ = _invoke_message(db, case, "What is an authorised photo studio?")

    # The graph correctly treats this as "no tool call, twice" — the
    # explicit no-relevant-match fallback — never as an instruction to
    # jump to `resolve` or skip verification.
    assert result.get("rag_answer") is None
    assert "resolution" not in result or result.get("resolution") is None


# --- 1.12: agent -> tools -> agent handles more than one tool call in one turn ---


def test_multiple_tool_calls_in_one_turn_all_execute_before_returning_to_agent(
    db, case, mock_agent_client
):
    renewal_fee = get_fee(db, "renewal", "normal")["fee"]["base_amount"]
    amendment_fee = get_fee(db, "amendment", "normal")["fee"]["base_amount"]

    mock_agent_client(
        tool_use_response(
            ("get_fee", {"service": "renewal", "urgency": "normal"}, "toolu_1"),
            ("get_fee", {"service": "amendment", "urgency": "normal"}, "toolu_2"),
        ),
        submit_answer_response(
            {
                "answer": f"Renewal is {renewal_fee}, amendment is {amendment_fee}.",
                "chunk_citations": [],
                "fee_values_used": [renewal_fee, amendment_fee],
                "office_names_used": [],
                "requirement_labels_used": [],
            }
        ),
    )

    result, _ = _invoke_message(db, case, "Should I amend my passport or get a new one?")

    assert result["rag_answer"] is not None
    trace = result["rag_answer"]["trace"]
    assert len(trace) == 2
    assert {t["tool"] for t in trace} == {"get_fee"}


# --- 1.13: a failed verify retries once, a second failure ends the turn ---


def test_failed_verification_retries_once_then_falls_back(db, case, mock_agent_client):
    bogus_submission = {
        "answer": "It costs 999999.",
        "chunk_citations": [],
        "fee_values_used": [999999.0],
        "office_names_used": [],
        "requirement_labels_used": [],
    }
    # Two consecutive submissions claiming a fee value no tool call ever
    # returned — verification fails both times.
    mock_agent_client(
        submit_answer_response(bogus_submission),
        submit_answer_response(bogus_submission),
    )

    result, _ = _invoke_message(db, case, "What is the fee for a name change amendment?")

    assert result["rag_answer"] is None
    # MAX_VERIFICATION_RETRIES=1 means one retry after the first
    # failure; the counter itself lands at 2 (the second, terminal
    # failure that pushed it past the budget).
    assert result.get("verification_retries") == 2


# --- 1.14: clearing the checkpoint never touches CASE_ANSWER ---


def test_clearing_the_checkpoint_does_not_lose_or_alter_case_answer_rows(
    db, renewal_service_id
):
    case = Case(service_id=renewal_service_id, device_ref="test-device-checkpoint-clear")
    db.add(case)
    db.commit()
    try:
        from app.engine.renewal_intake import RENEWAL_QUESTIONS
        from app.models import Question

        age_prompt = RENEWAL_QUESTIONS[0][1]
        question = db.query(Question).filter(
            Question.service_id == renewal_service_id, Question.prompt == age_prompt
        ).first()
        db.add(CaseAnswer(case_id=case.id, question_id=question.id, value="34"))
        db.commit()

        graph = get_compiled_graph()
        thread_id = f"test-clear-{case.id}"
        graph.invoke(
            {"action": "resolve", "case_id": str(case.id)},
            config={"configurable": {"thread_id": thread_id, "db": db}},
        )

        get_checkpointer().delete_thread(thread_id)

        recorded = db.query(CaseAnswer).filter(CaseAnswer.case_id == case.id).all()
        assert len(recorded) == 1
        assert recorded[0].value == "34"
    finally:
        db.query(CaseAnswer).filter(CaseAnswer.case_id == case.id).delete()
        db.query(Case).filter(Case.id == case.id).delete()
        db.commit()


# --- Manual-QA bug #2: the scope gate must fire the turn age<16 is
# recorded, on a message turn, not only on the explicit resolve action ---


def test_scope_gate_fires_immediately_on_the_message_turn_age_is_recorded(db, case, mock_agent_client):
    """Regression: an under-16 case used to keep being asked further
    questions (name_changed, dual_citizen, ...) for as long as the
    citizen kept answering, only refusing once resolve was eventually
    called. The very next response after age is recorded under 16 must
    be the scope-gate message, with no further question offered — even
    when the same message also happened to contain a question (the
    autouse classify mock always reports contains_question=True), the
    scope gate must still win over routing into the RAG/agent cycle."""
    from app.engine.renewal_intake import RENEWAL_QUESTIONS
    from app.engine.resolver import SCOPE_GATE_UNDER_16
    from app.models import Question

    age_prompt = RENEWAL_QUESTIONS[0][1]
    question = db.query(Question).filter(
        Question.service_id == case.service_id, Question.prompt == age_prompt
    ).first()
    db.add(CaseAnswer(case_id=case.id, question_id=question.id, value="15"))
    db.commit()

    result, _ = _invoke_message(db, case, "ok, what else do you need?")

    assert result.get("scope_gate_message") == SCOPE_GATE_UNDER_16
    assert result.get("next_pending_question_id") is None
    # Must not have fallen through into the agent/RAG cycle either.
    assert result.get("rag_answer") is None


# --- Manual-QA bug #3: a greeting is neither an answerable question nor
# a situation — it must not start intake or hit the RAG fallback ---


@pytest.mark.parametrize("message", ["hi", "help", "passport", "Hello", "  HELP  "])
def test_greeting_gets_an_orientation_not_a_question_or_rag_fallback(db, case, message):
    """Regression: "hi", "help", "passport" used to fall through to the
    classifier, misclassify as a question with nothing extracted, and
    produce "I don't have that information" plus the age question — for
    input that is neither a question nor a stated situation."""
    from app.graph.nodes import GREETING_ORIENTATION_MESSAGE

    result, _ = _invoke_message(db, case, message)

    assert result.get("greeting_message") == GREETING_ORIENTATION_MESSAGE
    assert result.get("next_pending_question_id") is None
    assert result.get("rag_answer") is None
    assert result.get("extracted") == {}
