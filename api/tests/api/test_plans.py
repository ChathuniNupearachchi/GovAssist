"""Item 7 — POST /plans/save, GET /plans, DELETE /plans/{id}.

Cases here are built directly against the DB (not driven through
`/chat/message`) — plans routes don't care how a case reached
`resolved_at`, only that it did; the intake path itself is covered
elsewhere (tests/api/test_routes.py, tests/graph/*).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.db.session import SessionLocal
from app.models import Case, SavedPlan, User


def _unique_email() -> str:
    return f"test-{uuid.uuid4().hex[:12]}@example.com"


def _signup(client, email: str) -> str:
    r = client.post("/auth/signup", json={"email": email, "password": "hunter22"})
    return r.json()["access_token"]


def _make_case(renewal_service_id, resolved: bool) -> uuid.UUID:
    db = SessionLocal()
    try:
        case = Case(
            service_id=renewal_service_id,
            device_ref=f"test-device-{uuid.uuid4().hex[:8]}",
            resolved_at=datetime.now(timezone.utc) if resolved else None,
        )
        db.add(case)
        db.commit()
        db.refresh(case)
        return case.id
    finally:
        db.close()


def _cleanup(email: str, case_id: uuid.UUID) -> None:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user is not None:
            db.query(SavedPlan).filter(SavedPlan.user_id == user.id).delete()
        db.query(SavedPlan).filter(SavedPlan.case_id == case_id).delete()
        db.query(Case).filter(Case.id == case_id).delete()
        if user is not None:
            db.delete(user)
        db.commit()
    finally:
        db.close()


def test_save_list_and_delete_a_plan(client, renewal_service_id):
    email = _unique_email()
    case_id = _make_case(renewal_service_id, resolved=True)
    try:
        token = _signup(client, email)
        headers = {"Authorization": f"Bearer {token}"}

        save = client.post(
            "/plans/save",
            json={"case_id": str(case_id), "label": "My renewal"},
            headers=headers,
        )
        assert save.status_code == 200
        plan_id = save.json()["id"]
        assert save.json()["label"] == "My renewal"

        listed = client.get("/plans", headers=headers)
        assert listed.status_code == 200
        assert [p["id"] for p in listed.json()] == [plan_id]

        deleted = client.delete(f"/plans/{plan_id}", headers=headers)
        assert deleted.status_code == 204

        listed_again = client.get("/plans", headers=headers)
        assert listed_again.json() == []
    finally:
        _cleanup(email, case_id)


def test_a_citizen_can_hold_several_plans_at_once(client, renewal_service_id):
    """A parent renewing their own passport and applying for a child's
    should see two clearly labelled entries."""
    email = _unique_email()
    case_id_1 = _make_case(renewal_service_id, resolved=True)
    case_id_2 = _make_case(renewal_service_id, resolved=True)
    try:
        token = _signup(client, email)
        headers = {"Authorization": f"Bearer {token}"}

        client.post("/plans/save", json={"case_id": str(case_id_1), "label": "My renewal"}, headers=headers)
        client.post(
            "/plans/save", json={"case_id": str(case_id_2), "label": "My daughter's passport"}, headers=headers
        )

        listed = client.get("/plans", headers=headers)
        labels = {p["label"] for p in listed.json()}
        assert labels == {"My renewal", "My daughter's passport"}
    finally:
        _cleanup(email, case_id_1)
        _cleanup(email, case_id_2)


def test_cannot_save_an_unresolved_case(client, renewal_service_id):
    email = _unique_email()
    case_id = _make_case(renewal_service_id, resolved=False)
    try:
        token = _signup(client, email)
        headers = {"Authorization": f"Bearer {token}"}

        r = client.post("/plans/save", json={"case_id": str(case_id), "label": "Not ready"}, headers=headers)
        assert r.status_code == 400
    finally:
        _cleanup(email, case_id)


def test_saving_requires_a_valid_token(client, renewal_service_id):
    case_id = _make_case(renewal_service_id, resolved=True)
    try:
        r = client.post("/plans/save", json={"case_id": str(case_id), "label": "Nope"})
        assert r.status_code == 401
    finally:
        _cleanup("unused@example.com", case_id)


def test_a_user_cannot_delete_another_users_plan(client, renewal_service_id):
    email_a = _unique_email()
    email_b = _unique_email()
    case_id = _make_case(renewal_service_id, resolved=True)
    try:
        token_a = _signup(client, email_a)
        token_b = _signup(client, email_b)

        save = client.post(
            "/plans/save",
            json={"case_id": str(case_id), "label": "A's plan"},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        plan_id = save.json()["id"]

        deleted = client.delete(f"/plans/{plan_id}", headers={"Authorization": f"Bearer {token_b}"})
        assert deleted.status_code == 404

        # Still there for its actual owner.
        listed = client.get("/plans", headers={"Authorization": f"Bearer {token_a}"})
        assert [p["id"] for p in listed.json()] == [plan_id]
    finally:
        _cleanup(email_a, case_id)
        _cleanup(email_b, case_id)
