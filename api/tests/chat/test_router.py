"""Unit tests for chat.router.handle_message (6.1) — since task 1.9 of
`langgraph-orchestration-branch`, this is a thin re-export of
`app.graph.build.run_message_turn`, itself calling the compiled graph.

Mocks `app.graph.nodes._classify` (the classifier) and the Anthropic
client the `agent` node uses (the agent's model turn) — these are
already covered by their own real-API tests (test_classifier.py,
tests/chat/test_agent.py); what these tests exercise is the same
decision logic the pre-graph router had (deterministic vs. Claude path,
when RAG fires, what gets recorded), now living in `app.graph.nodes`/
`app.graph.agent_nodes`, isolated from live model variance for the same
reason the original tests were.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.chat import router as chat_router
from app.chat.classifier import Classification, ExtractedFacts
from app.engine.renewal_intake import RENEWAL_QUESTIONS
from app.graph import agent_nodes, nodes as graph_nodes
from app.models import Case, CaseAnswer

FIRST_QUESTION_PROMPT = RENEWAL_QUESTIONS[0][1]  # "How old is the applicant?"


@pytest.fixture()
def case(db, renewal_service_id):
    c = Case(service_id=renewal_service_id, device_ref="test-device-router")
    db.add(c)
    db.commit()
    yield c
    db.query(CaseAnswer).filter(CaseAnswer.case_id == c.id).delete()
    db.delete(c)
    db.commit()


def _text_response():
    return SimpleNamespace(
        stop_reason="end_turn",
        content=[SimpleNamespace(type="text", text="I don't have that information.")],
    )


def _submit_answer_response(text: str):
    return SimpleNamespace(
        stop_reason="tool_use",
        content=[
            SimpleNamespace(
                type="tool_use",
                id="toolu_submit",
                name="submit_answer",
                input={
                    "answer": text,
                    "chunk_citations": [],
                    "fee_values_used": [],
                    "office_names_used": [],
                    "requirement_labels_used": [],
                },
            )
        ],
    )


class _FakeMessages:
    def __init__(self, responses):
        self._responses = list(responses)

    def create(self, **kwargs):
        if len(self._responses) > 1:
            return self._responses.pop(0)
        return self._responses[0]


class _FakeAnthropicClient:
    def __init__(self, responses):
        self.messages = _FakeMessages(responses)


def _mock_agent_client(monkeypatch, *responses):
    # `agent_node` calls `anthropic.Anthropic()` fresh on every node
    # invocation — build the fake client (and its response-consumption
    # state) once and reuse the same instance across calls, or it never
    # advances past the first response (see tests/graph/conftest.py's
    # identical fix for the same bug).
    shared_client = _FakeAnthropicClient(responses)
    monkeypatch.setattr(agent_nodes.anthropic, "Anthropic", lambda: shared_client)


def test_deterministic_match_records_answer_with_no_rag_call(db, case, monkeypatch):
    def _fail_if_called():
        raise AssertionError("RAG should not be called on a deterministic match")

    monkeypatch.setattr(agent_nodes.anthropic, "Anthropic", _fail_if_called)

    outcome = chat_router.handle_message(db, case, "34")
    db.commit()

    assert outcome.rag_response is None
    recorded = db.query(CaseAnswer).filter(CaseAnswer.case_id == case.id).all()
    assert len(recorded) == 1
    assert recorded[0].value == "34"
    # Next pending question has moved past "age".
    assert outcome.next_pending_question is not None
    assert outcome.next_pending_question.prompt != FIRST_QUESTION_PROMPT


def test_combined_message_records_fact_and_answers_question_in_one_call(
    db, case, monkeypatch
):
    fake_classification = Classification(
        intent="situation",
        extracted=ExtractedFacts(name_changed="true"),
        contains_question=True,
        confidence=0.95,
    )
    monkeypatch.setattr(graph_nodes, "_classify", lambda *a, **k: fake_classification)
    _mock_agent_client(monkeypatch, _submit_answer_response("Amendments cost LKR 1,200."))

    outcome = chat_router.handle_message(
        db, case, "My name changed after marriage — what does that mean for the fee?"
    )
    db.commit()

    assert outcome.rag_response is not None
    assert outcome.rag_response.text == "Amendments cost LKR 1,200."
    assert outcome.rag_response.grounded is True

    recorded = db.query(CaseAnswer).filter(CaseAnswer.case_id == case.id).all()
    assert len(recorded) == 1
    assert recorded[0].value == "true"


def test_low_confidence_leaves_pending_question_unanswered(db, case, monkeypatch):
    # classify() already applies the low-confidence override internally;
    # here we simulate its post-override output directly to test the
    # router's handling of it.
    low_confidence_result = Classification(
        intent="question",
        extracted=ExtractedFacts(),
        contains_question=True,
        confidence=0.2,
    )
    monkeypatch.setattr(graph_nodes, "_classify", lambda *a, **k: low_confidence_result)
    # No tool call at all, twice in a row (the agent node's one
    # "try a tool before giving up" nudge, then the real give-up) — the
    # explicit no-relevant-match outcome.
    _mock_agent_client(monkeypatch, _text_response(), _text_response())

    outcome = chat_router.handle_message(db, case, "hmm, not totally sure")
    db.commit()

    recorded = db.query(CaseAnswer).filter(CaseAnswer.case_id == case.id).all()
    assert len(recorded) == 0
    assert outcome.next_pending_question is not None
    assert outcome.next_pending_question.prompt == FIRST_QUESTION_PROMPT
    assert outcome.rag_response is not None
    assert outcome.rag_response.grounded is False
