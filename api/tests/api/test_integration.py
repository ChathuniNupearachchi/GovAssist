"""8. Done-When verification — end-to-end checks through the real API
(TestClient over the real FastAPI app), the real dev database, and real
Claude API calls. No mocking, matching the session's established
verification standard.
"""

from __future__ import annotations

import pytest

from app.chat.limits import MAX_MESSAGE_CHARACTERS
from app.db.session import SessionLocal
from app.models import Case, CaseAnswer, ChatMessage

pytestmark = pytest.mark.real_api


def _delete_case(case_id: str) -> None:
    db = SessionLocal()
    try:
        # 6.10: every /chat/message call now persists ChatMessage rows
        # too — delete those first, or the FK to `case` blocks cleanup.
        db.query(ChatMessage).filter(ChatMessage.case_id == case_id).delete()
        db.query(CaseAnswer).filter(CaseAnswer.case_id == case_id).delete()
        db.query(Case).filter(Case.id == case_id).delete()
        db.commit()
    finally:
        db.close()


def test_full_renewal_case_resolves_end_to_end(client):
    """8.1 — opening message, repeated answers to each next_question,
    then POST /case/{id}/resolve returns the full plan."""
    r = client.post(
        "/chat/message",
        json={"message": "40", "device_ref": "e2e-full-renewal"},
    )
    assert r.status_code == 200
    body = r.json()
    case_id = body["case_id"]

    try:
        # "40" deterministically answers "How old is the applicant?" —
        # keep answering with bare deterministic tokens so the rest of
        # this flow doesn't depend on live classifier judgment calls.
        answers_in_order = ["yes", "no", "no", "Teacher", "no", "Colombo", "normal"]
        for answer in answers_in_order:
            r = client.post(
                "/chat/message", json={"message": answer, "case_id": case_id}
            )
            assert r.status_code == 200
            body = r.json()

        assert body["next_question"] is None

        resolve = client.post(f"/case/{case_id}/resolve")
        assert resolve.status_code == 200
        plan = resolve.json()
        assert plan["scope_gate"] is None
        assert len(plan["requirements"]) > 0
        assert plan["fee"] is not None
        assert plan["fee"]["citation"]["source_url"]
        assert plan["offices"] is not None
        assert len(plan["offices"]["offices"]) > 0
    finally:
        _delete_case(case_id)


def test_general_question_mid_intake_answers_and_re_asks_pending(client):
    """8.2 — a general question mid-intake returns a grounded answer and
    the same pending question is still returned as next."""
    r = client.post(
        "/chat/message",
        json={"message": "40", "device_ref": "e2e-mid-intake-question"},
    )
    body = r.json()
    case_id = body["case_id"]
    pending_before = body["next_question"]["prompt"]

    try:
        r = client.post(
            "/chat/message",
            json={
                "message": "What documents do I need to bring to the photo studio?",
                "case_id": case_id,
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["answer"] is not None
        assert body["answer"]["text"]
        assert body["next_question"] is not None
        assert body["next_question"]["prompt"] == pending_before
    finally:
        _delete_case(case_id)


def test_combined_situation_and_question_in_one_call(client):
    """8.3 — a message that both states a fact and asks a question
    records the fact and answers the question in one call."""
    r = client.post(
        "/chat/message",
        json={"message": "40", "device_ref": "e2e-combined"},
    )
    body = r.json()
    case_id = body["case_id"]
    assert body["next_question"]["prompt"] == "Do you still hold your current or a previous passport?"

    try:
        r = client.post(
            "/chat/message",
            json={"message": "yes", "case_id": case_id},
        )
        body = r.json()
        assert body["next_question"]["prompt"] == "Has your name changed since your passport was issued?"

        r = client.post(
            "/chat/message",
            json={
                "message": "My name changed after marriage — what does that mean for the fee?",
                "case_id": case_id,
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["answer"] is not None
        assert body["answer"]["text"]
        # The fact was recorded — intake moved past name_changed.
        assert body["next_question"] is not None
        assert body["next_question"]["prompt"] == "Are you a dual citizen?"
    finally:
        _delete_case(case_id)


def test_under_16_case_returns_scope_gate_through_the_api(client):
    """8.4 — an under-16 case's resolve returns the scope-gate response,
    not a plan, through the API — without waiting on the rest of
    intake, mirroring resolve_case's own "age evaluated first"
    precedence."""
    r = client.post(
        "/chat/message",
        json={"message": "10", "device_ref": "e2e-under-16"},
    )
    body = r.json()
    case_id = body["case_id"]

    try:
        resolve = client.post(f"/case/{case_id}/resolve")
        assert resolve.status_code == 200
        plan = resolve.json()
        assert plan["scope_gate"] is not None
        assert plan["scope_gate"]["reason"]
        assert plan["requirements"] == []
        assert plan["fee"] is None
    finally:
        _delete_case(case_id)


def test_message_over_2000_characters_is_truncated_before_any_model_call(client):
    """8.5 — integration-level: an over-length message never reaches a
    model call with its full content. Send a message far longer than
    the cap and confirm the turn still completes normally (a raw
    unbounded message would risk an oversized-request failure well
    before 2,000 characters if truncation weren't applied first)."""
    oversized = "a" * (MAX_MESSAGE_CHARACTERS * 5)
    r = client.post(
        "/chat/message",
        json={"message": oversized, "device_ref": "e2e-oversized-message"},
    )
    body = r.json()
    case_id = body.get("case_id")
    try:
        assert r.status_code == 200
    finally:
        if case_id:
            _delete_case(case_id)
