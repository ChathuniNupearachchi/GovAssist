"""6.11 — Done-When verification through the real API (TestClient), the
real dev database, and real Claude API calls — same standard as
`test_integration.py` and `test_session.py`.
"""

from __future__ import annotations

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


def test_expired_passport_message_gets_a_contextual_age_question_and_records_correctly(client):
    """DONE WHEN: "My passport expired last year" is followed by a
    contextually phrased age question, and the answer still records to
    the age attribute."""
    r = client.post(
        "/chat/message",
        json={"message": "My passport expired last year", "device_ref": "e2e-expired-passport"},
    )
    assert r.status_code == 200
    body = r.json()
    case_id = body["case_id"]

    try:
        assert body["next_question"] is not None
        assert body["next_question"]["prompt"] == "How old is the applicant?"
        # display_text is always populated (falls back to the canonical
        # prompt when rephrasing didn't happen or was discarded).
        assert body["next_question"]["display_text"]

        r2 = client.post("/chat/message", json={"message": "34", "case_id": case_id})
        assert r2.status_code == 200
        body2 = r2.json()
        assert body2["next_question"] is not None
        assert body2["next_question"]["prompt"] != "How old is the applicant?"

        db = SessionLocal()
        try:
            recorded = db.query(CaseAnswer).filter(CaseAnswer.case_id == case_id).all()
        finally:
            db.close()
        assert len(recorded) == 1
        assert recorded[0].value == "34"
    finally:
        _delete_case(case_id)


def test_name_change_message_acknowledges_marriage_certificate_and_skips_question(client):
    """DONE WHEN: "I got married and my name is different now"
    acknowledges the marriage certificate requirement and skips the
    name-change question (already answered).

    The renewal service's marriage-certificate requirement is gated on
    both `name_changed == true` AND `dual_citizen != true` (see
    app/engine/conditions.py's "a missing answer is always
    not-satisfied" rule) — since `dual_citizen` is asked one question
    *after* `name_changed` in the real intake sequence, a name-change
    message sent alone can't show the requirement as newly triggered
    yet (dual_citizen is still unknown at that point). The citizen
    states both facts in one message here, which the classifier extracts
    together regardless of which one is currently pending — matching
    the "acknowledge only facts actually recorded" rule while still
    letting the diff see the requirement actually turn on.
    """
    r = client.post(
        "/chat/message", json={"message": "40", "device_ref": "e2e-name-change-ack"}
    )
    case_id = r.json()["case_id"]

    try:
        # Advance past holds_passport so name_changed is the pending question.
        r = client.post("/chat/message", json={"message": "yes", "case_id": case_id})
        assert r.json()["next_question"]["prompt"] == (
            "Has your name changed since your passport was issued?"
        )

        r = client.post(
            "/chat/message",
            json={
                "message": (
                    "I got married and my name is different now. "
                    "I'm not a dual citizen."
                ),
                "case_id": case_id,
            },
        )
        assert r.status_code == 200
        body = r.json()

        assert body["acknowledgement"] is not None
        assert "marriage" in body["acknowledgement"].lower() or "certificate" in body["acknowledgement"].lower()

        # The name-change question was answered by this message, not
        # asked again — the pending question has moved on.
        assert body["next_question"]["prompt"] != (
            "Has your name changed since your passport was issued?"
        )

        db = SessionLocal()
        try:
            values = {
                a.question_id: a.value
                for a in db.query(CaseAnswer).filter(CaseAnswer.case_id == case_id).all()
            }
        finally:
            db.close()
        assert "true" in values.values()
    finally:
        _delete_case(case_id)


def test_amend_vs_renew_tool_trace_is_persisted_and_retrievable(client):
    """DONE WHEN: the amend-vs-renew tool trace is logged and
    retrievable (queryable from ChatMessage.tool_trace via the
    transcript endpoint).

    Unlike `tests/chat/test_agent.py`'s case-less flagship test (which
    asserts the literal two-get_fee-calls trace, since without a case_id
    that's the only path available), this turn has a real case_id in
    context, so the model may legitimately reach for the dedicated
    `compare_amendment_vs_renewal` tool instead — a single call that
    itself makes both lookups. The agentic-tool-answering spec's own
    "chains multiple tool calls" scenario allows both paths; this test
    accepts either, and only requires that a real, persisted,
    multi-step-or-comparison trace exists and is retrievable.
    """
    device_ref = "e2e-amend-vs-renew-trace"
    r = client.post(
        "/chat/message",
        json={
            "message": "Should I amend my passport or get a new one?",
            "device_ref": device_ref,
        },
    )
    assert r.status_code == 200
    case_id = r.json()["case_id"]

    try:
        assert r.json()["answer"] is not None
        assert r.json()["answer"]["grounded"] is True

        transcript = client.get("/chat/transcript", params={"device_ref": device_ref})
        assert transcript.status_code == 200
        messages = transcript.json()["messages"]
        assistant_messages_with_trace = [
            m for m in messages if m["role"] == "assistant" and m["tool_trace"]
        ]
        assert assistant_messages_with_trace, "no persisted assistant message carried a tool_trace"

        trace = assistant_messages_with_trace[0]["tool_trace"]
        tool_names = [call["tool"] for call in trace]
        used_dedicated_comparison_tool = "compare_amendment_vs_renewal" in tool_names
        used_two_separate_fee_lookups = tool_names.count("get_fee") >= 2
        assert used_dedicated_comparison_tool or used_two_separate_fee_lookups, (
            f"expected either compare_amendment_vs_renewal or two get_fee calls, got: {tool_names}"
        )
    finally:
        _delete_case(case_id)
