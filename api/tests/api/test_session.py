"""6.10 — Done-When verification for persistent session memory, through
the real API (TestClient), the real dev database, and (where a chat
turn is involved) real Claude classification calls — same standard as
`test_integration.py`. Deterministic answer tokens ("40", "yes") are
used wherever possible to keep these fast and to isolate session
behavior from classifier judgment calls, matching that file's own
convention.
"""

from __future__ import annotations

from app.chat.session import _invalidate_session_cache
from app.db.session import SessionLocal
from app.models import Case, CaseAnswer, ChatMessage


def _delete_case(case_id: str) -> None:
    db = SessionLocal()
    try:
        db.query(ChatMessage).filter(ChatMessage.case_id == case_id).delete()
        db.query(CaseAnswer).filter(CaseAnswer.case_id == case_id).delete()
        db.query(Case).filter(Case.id == case_id).delete()
        db.commit()
    finally:
        db.close()


def test_returning_device_resumes_case_with_prior_conversation(client):
    """A case interrupted mid-intake and resumed (same device_ref,
    case_id omitted — simulating the app reopening) returns both the
    correct next question and the prior conversation, not a fresh
    case."""
    device_ref = "e2e-resume-mid-intake"
    r1 = client.post("/chat/message", json={"message": "40", "device_ref": device_ref})
    assert r1.status_code == 200
    case_id = r1.json()["case_id"]

    try:
        # Simulated app reopen: device_ref only, no case_id.
        r2 = client.post("/chat/message", json={"message": "yes", "device_ref": device_ref})
        assert r2.status_code == 200
        body2 = r2.json()
        assert body2["case_id"] == case_id, "a returning device got a new case, not its own"
        assert body2["next_question"] is not None  # intake isn't complete yet

        transcript = client.get("/chat/transcript", params={"device_ref": device_ref})
        assert transcript.status_code == 200
        messages = transcript.json()["messages"]
        contents = [m["content"] for m in messages]
        assert "40" in contents
        assert "yes" in contents
    finally:
        _delete_case(case_id)


def test_closing_and_reopening_restores_the_visible_transcript(client):
    """Closing and reopening restores the visible transcript, not just
    the engine's resolved facts — every message exchanged, in order.
    Since 6.11.3, a turn that triggers a newly-required requirement (age
    40 triggers the fingerprints prerequisite) also persists an
    acknowledgement message alongside the citizen's own — this asserts
    the citizen's own two messages are both present and in order, not
    that they're the transcript's only messages."""
    device_ref = "e2e-restore-transcript"
    r1 = client.post("/chat/message", json={"message": "40", "device_ref": device_ref})
    case_id = r1.json()["case_id"]

    try:
        client.post("/chat/message", json={"message": "no", "device_ref": device_ref})

        transcript = client.get("/chat/transcript", params={"device_ref": device_ref})
        body = transcript.json()
        assert body["case_id"] == case_id
        user_contents_in_order = [
            m["content"] for m in body["messages"] if m["role"] == "user"
        ]
        assert user_contents_in_order == ["40", "no"]
    finally:
        _delete_case(case_id)


def test_new_device_starts_cleanly(client):
    """A device with no prior case gets an empty transcript, not an
    error and not someone else's case."""
    response = client.get(
        "/chat/transcript", params={"device_ref": "e2e-brand-new-device-never-seen"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["case_id"] is None
    assert body["messages"] == []


def test_transcript_restores_after_redis_is_cleared(client):
    """Redis holds the hot session; Postgres holds the durable record.
    Clearing the Redis cache for this case must not lose the
    transcript — it's reconstructed from Postgres instead. Compares the
    transcript before and after clearing the cache, rather than a fixed
    expected message count, since 6.11.3 may add an acknowledgement
    message alongside the citizen's own for this same turn."""
    device_ref = "e2e-redis-cleared"
    r1 = client.post("/chat/message", json={"message": "40", "device_ref": device_ref})
    case_id = r1.json()["case_id"]

    try:
        before = client.get("/chat/transcript", params={"device_ref": device_ref}).json()

        _invalidate_session_cache(case_id)  # simulate the hot cache being cleared

        transcript = client.get("/chat/transcript", params={"device_ref": device_ref})
        assert transcript.status_code == 200
        body = transcript.json()
        assert body["case_id"] == case_id
        assert [m["content"] for m in body["messages"]] == [
            m["content"] for m in before["messages"]
        ]
        assert any(m["content"] == "40" for m in body["messages"])
    finally:
        _delete_case(case_id)


def test_resolved_case_is_not_resumed_as_still_in_progress(client):
    """A device whose only prior case has already been resolved starts
    a fresh case next time, rather than being stuck "continuing" a
    finished one."""
    device_ref = "e2e-resolved-not-resumed"
    r1 = client.post("/chat/message", json={"message": "40", "device_ref": device_ref})
    first_case_id = r1.json()["case_id"]

    try:
        for answer in ["yes", "no", "no", "Teacher", "no", "Colombo", "normal"]:
            r = client.post(
                "/chat/message", json={"message": answer, "case_id": first_case_id}
            )
        assert r.json()["next_question"] is None

        resolve = client.post(f"/case/{first_case_id}/resolve")
        assert resolve.status_code == 200

        r2 = client.post(
            "/chat/message", json={"message": "45", "device_ref": device_ref}
        )
        second_case_id = r2.json()["case_id"]
        assert second_case_id != first_case_id, (
            "a device whose only case was already resolved got that same "
            "resolved case back instead of a fresh one"
        )
        _delete_case(second_case_id)
    finally:
        _delete_case(first_case_id)
