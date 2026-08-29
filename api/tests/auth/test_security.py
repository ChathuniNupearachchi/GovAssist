"""Item 7 — password hashing and JWT round-trip, isolated from the DB/
HTTP layer (see tests/api/test_auth.py for the route-level behavior)."""

from __future__ import annotations

import uuid

import jwt as pyjwt
import pytest

from app.auth.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_password_never_stores_the_plaintext():
    hashed = hash_password("hunter22")
    assert hashed != "hunter22"


def test_verify_password_accepts_the_correct_password():
    hashed = hash_password("hunter22")
    assert verify_password("hunter22", hashed) is True


def test_verify_password_rejects_the_wrong_password():
    hashed = hash_password("hunter22")
    assert verify_password("wrong-password", hashed) is False


def test_verify_password_rejects_a_malformed_stored_hash_without_raising():
    assert verify_password("hunter22", "not-a-real-bcrypt-hash") is False


def test_access_token_round_trips_to_the_same_user_id():
    user_id = uuid.uuid4()
    token = create_access_token(user_id)
    assert decode_access_token(token) == user_id


def test_decode_rejects_a_garbage_token():
    assert decode_access_token("not.a.jwt") is None


def test_decode_rejects_a_token_signed_with_a_different_key():
    user_id = uuid.uuid4()
    forged = pyjwt.encode({"sub": str(user_id)}, "wrong-secret", algorithm="HS256")
    assert decode_access_token(forged) is None


def test_decode_rejects_an_expired_token():
    from datetime import datetime, timedelta, timezone

    from app.auth.security import JWT_ALGORITHM, _secret_key

    user_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    expired = pyjwt.encode(
        {"sub": str(user_id), "iat": now - timedelta(minutes=10), "exp": now - timedelta(minutes=1)},
        _secret_key(),
        algorithm=JWT_ALGORITHM,
    )
    assert decode_access_token(expired) is None
