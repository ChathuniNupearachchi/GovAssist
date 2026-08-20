"""Unit tests for chat.router.handle_message (6.1).

Mocks classify() and answer_question() — these are already covered by
their own real-API tests (test_classifier.py, Phase 5's RAG tests); what
these tests exercise is the router's own decision logic (deterministic
vs. Claude path, when RAG fires, what gets recorded), so isolating it
from live model variance is the right call here, not a reliability
workaround.
"""

from __future__ import annotations

import pytest

from app.chat import router as chat_router
from app.chat.classifier import Classification, ExtractedFacts
from app.engine.renewal_intake import RENEWAL_QUESTIONS
from app.models import Case, CaseAnswer
from app.rag.answer import RAGResponse

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


def test_deterministic_match_records_answer_with_no_rag_call(db, case, monkeypatch):
    def _fail_if_called(*args, **kwargs):
        raise AssertionError("RAG should not be called on a deterministic match")

    monkeypatch.setattr(chat_router, "answer_question", _fail_if_called)

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
    monkeypatch.setattr(chat_router, "classify", lambda *a, **k: fake_classification)

    fake_answer = RAGResponse(text="Amendments cost LKR 1,200.", citations=[], grounded=True)
    call_count = {"n": 0}

    def _fake_answer_question(db_arg, query, case_id=None):
        call_count["n"] += 1
        return fake_answer

    monkeypatch.setattr(chat_router, "answer_question", _fake_answer_question)

    outcome = chat_router.handle_message(
        db, case, "My name changed after marriage — what does that mean for the fee?"
    )
    db.commit()

    assert call_count["n"] == 1
    assert outcome.rag_response is fake_answer

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
    monkeypatch.setattr(chat_router, "classify", lambda *a, **k: low_confidence_result)
    monkeypatch.setattr(
        chat_router,
        "answer_question",
        lambda db_arg, query, case_id=None: RAGResponse(
            text="I don't have that information.", citations=[], grounded=False
        ),
    )

    outcome = chat_router.handle_message(db, case, "hmm, not totally sure")
    db.commit()

    recorded = db.query(CaseAnswer).filter(CaseAnswer.case_id == case.id).all()
    assert len(recorded) == 0
    assert outcome.next_pending_question is not None
    assert outcome.next_pending_question.prompt == FIRST_QUESTION_PROMPT
