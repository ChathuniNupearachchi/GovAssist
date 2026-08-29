"""admin-dashboard change, task 3.5 — signup, signin, duplicate-email
rejection, wrong-password rejection, protected-route-without-token
rejection, and a citizen-facing JWT rejected on an admin route."""

from __future__ import annotations

import uuid

import jwt

from tests.conftest import client


def _unique_email() -> str:
    return f"admin-{uuid.uuid4().hex[:12]}@example.test"


def test_signup_creates_admin_and_returns_token():
    response = client.post(
        "/admin/auth/signup",
        json={"email": _unique_email(), "password": "correct horse battery staple", "role": "reviewer"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_signup_duplicate_email_rejected():
    email = _unique_email()
    first = client.post(
        "/admin/auth/signup", json={"email": email, "password": "correct horse battery staple", "role": "reviewer"}
    )
    assert first.status_code == 200

    second = client.post(
        "/admin/auth/signup", json={"email": email, "password": "a different password", "role": "reviewer"}
    )
    assert second.status_code == 409


def test_signin_succeeds_with_correct_credentials():
    email = _unique_email()
    password = "correct horse battery staple"
    client.post("/admin/auth/signup", json={"email": email, "password": password, "role": "approver"})

    response = client.post("/admin/auth/signin", json={"email": email, "password": password})
    assert response.status_code == 200
    assert response.json()["access_token"]


def test_signin_wrong_password_rejected():
    email = _unique_email()
    client.post("/admin/auth/signup", json={"email": email, "password": "correct horse battery staple", "role": "reviewer"})

    response = client.post("/admin/auth/signin", json={"email": email, "password": "wrong password entirely"})
    assert response.status_code == 401


def test_protected_route_without_token_rejected():
    response = client.get("/admin/dashboard/summary")
    assert response.status_code == 401


def test_protected_route_with_citizen_token_rejected():
    # A token signed the way the citizen-facing app signs its own
    # (`sub`, no `aud` claim) — even if it somehow used the same secret,
    # ADMIN_JWT_SECRET_KEY and JWT_SECRET_KEY are independent env vars,
    # so this simulates the shape a citizen token would have.
    fake_citizen_token = jwt.encode(
        {"sub": str(uuid.uuid4())}, "not-the-admin-secret", algorithm="HS256"
    )
    response = client.get(
        "/admin/dashboard/summary", headers={"Authorization": f"Bearer {fake_citizen_token}"}
    )
    assert response.status_code == 401


def test_both_roles_reach_the_same_dashboard():
    reviewer_email = _unique_email()
    approver_email = _unique_email()
    password = "correct horse battery staple"

    reviewer_token = client.post(
        "/admin/auth/signup", json={"email": reviewer_email, "password": password, "role": "reviewer"}
    ).json()["access_token"]
    approver_token = client.post(
        "/admin/auth/signup", json={"email": approver_email, "password": password, "role": "approver"}
    ).json()["access_token"]

    for token in (reviewer_token, approver_token):
        response = client.get("/admin/dashboard/summary", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
