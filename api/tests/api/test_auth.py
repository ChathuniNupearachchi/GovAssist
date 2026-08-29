"""Item 7 — POST /auth/signup, POST /auth/signin."""

from __future__ import annotations

import uuid

from app.db.session import SessionLocal
from app.models import User


def _delete_user_by_email(email: str) -> None:
    db = SessionLocal()
    try:
        db.query(User).filter(User.email == email).delete()
        db.commit()
    finally:
        db.close()


def _unique_email() -> str:
    return f"test-{uuid.uuid4().hex[:12]}@example.com"


def test_signup_creates_account_and_returns_a_token(client):
    email = _unique_email()
    try:
        r = client.post("/auth/signup", json={"email": email, "password": "hunter22"})
        assert r.status_code == 200
        body = r.json()
        assert body["token_type"] == "bearer"
        assert body["access_token"]
    finally:
        _delete_user_by_email(email)


def test_signup_rejects_a_duplicate_email(client):
    email = _unique_email()
    try:
        r1 = client.post("/auth/signup", json={"email": email, "password": "hunter22"})
        assert r1.status_code == 200

        r2 = client.post("/auth/signup", json={"email": email, "password": "different1"})
        assert r2.status_code == 409
    finally:
        _delete_user_by_email(email)


def test_signup_rejects_a_short_password(client):
    email = _unique_email()
    r = client.post("/auth/signup", json={"email": email, "password": "short"})
    assert r.status_code == 422


def test_signup_rejects_an_invalid_email(client):
    r = client.post("/auth/signup", json={"email": "not-an-email", "password": "hunter22"})
    assert r.status_code == 422


def test_signin_with_correct_password_returns_a_token(client):
    email = _unique_email()
    try:
        client.post("/auth/signup", json={"email": email, "password": "hunter22"})

        r = client.post("/auth/signin", json={"email": email, "password": "hunter22"})
        assert r.status_code == 200
        assert r.json()["access_token"]
    finally:
        _delete_user_by_email(email)


def test_signin_with_wrong_password_is_rejected(client):
    email = _unique_email()
    try:
        client.post("/auth/signup", json={"email": email, "password": "hunter22"})

        r = client.post("/auth/signin", json={"email": email, "password": "wrong-password"})
        assert r.status_code == 401
    finally:
        _delete_user_by_email(email)


def test_signin_with_unknown_email_is_rejected(client):
    r = client.post("/auth/signin", json={"email": _unique_email(), "password": "hunter22"})
    assert r.status_code == 401


def test_signin_is_case_insensitive_on_email(client):
    email = _unique_email()
    try:
        client.post("/auth/signup", json={"email": email, "password": "hunter22"})

        r = client.post("/auth/signin", json={"email": email.upper(), "password": "hunter22"})
        assert r.status_code == 200
    finally:
        _delete_user_by_email(email)
