"""5.x route-level tests — route wiring, request/response shape, and the
error paths that keep `/case/{id}/resolve` from ever leaking an
unhandled 500 (design.md's "does not itself drive intake" decision).
"""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import Case, CaseAnswer, ChatMessage, Requirement


def _delete_case(case_id):
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


def test_openapi_json_renders(client):
    r = client.get("/openapi.json")
    assert r.status_code == 200
    assert "paths" in r.json()


def test_docs_renders(client):
    r = client.get("/docs")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_chat_message_without_case_id_or_device_ref_is_rejected(client):
    r = client.post("/chat/message", json={"message": "hello"})
    assert r.status_code == 422


def test_chat_message_creates_case_when_absent(client):
    r = client.post(
        "/chat/message",
        json={"message": "34", "device_ref": "route-test-device"},
    )
    body = r.json()
    try:
        assert r.status_code == 200
        assert uuid.UUID(body["case_id"])
        assert body["next_question"] is not None
    finally:
        if "case_id" in body:
            _delete_case(body["case_id"])


def test_case_not_found_returns_404(client):
    r = client.get(f"/case/{uuid.uuid4()}/next-question")
    assert r.status_code == 404


def test_resolve_not_ready_returns_409_naming_pending_question(client):
    create = client.post(
        "/chat/message",
        json={"message": "hi", "device_ref": "route-test-device-2"},
    )
    case_id = create.json()["case_id"]
    try:
        r = client.post(f"/case/{case_id}/resolve")
        assert r.status_code == 409
        assert "pending" in r.json()["detail"].lower()
    finally:
        _delete_case(case_id)


def test_services_lists_available_services(client):
    r = client.get("/services")
    assert r.status_code == 200
    codes = {s["code"] for s in r.json()}
    assert "passport-renewal" in codes
    assert "passport-amendment" in codes


def test_requirement_detail_includes_citation(client):
    db = SessionLocal()
    try:
        requirement = db.scalars(select(Requirement)).first()
    finally:
        db.close()
    assert requirement is not None

    r = client.get(f"/requirements/{requirement.id}")
    assert r.status_code == 200
    body = r.json()
    assert body["citation"]["source_url"]


def test_requirement_detail_404_for_unknown_id(client):
    r = client.get(f"/requirements/{uuid.uuid4()}")
    assert r.status_code == 404
