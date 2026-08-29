"""admin-dashboard change, task 3.1 — bcrypt hashing and JWT signing/
verification for the admin dashboard's own, independent token space.

Mirrors `api/app/auth/security.py`'s pattern (bcrypt directly, PyJWT
HS256) exactly, but copied rather than imported — see design.md's
"Admin auth mirrors, but does not share, citizen auth" decision. Signs
under `ADMIN_JWT_SECRET_KEY` (admin/api/.env), a token space entirely
independent of the citizen app's `JWT_SECRET_KEY`, and a shorter 8-hour
lifetime (a work session, not a mobile app a citizen shouldn't be
signed out of).
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from dotenv import load_dotenv

load_dotenv()

JWT_ALGORITHM = "HS256"
JWT_EXPIRES_MINUTES = 60 * 8  # 8 hours — a reviewer's work session.


def _secret_key() -> str:
    key = os.environ.get("ADMIN_JWT_SECRET_KEY")
    if not key:
        raise RuntimeError(
            "ADMIN_JWT_SECRET_KEY is not set — required for /admin/auth/signup and "
            "/admin/auth/signin. Set it in admin/api/.env."
        )
    return key


def hash_password(plain_password: str) -> str:
    return bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        # A malformed/corrupt stored hash — never a reason to raise into
        # a 500; treat exactly like a wrong password.
        return False


def create_access_token(admin_id: uuid.UUID) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(admin_id),
        "iat": now,
        "exp": now + timedelta(minutes=JWT_EXPIRES_MINUTES),
        # Distinguishes an admin token from a citizen-facing one even if
        # the two secrets ever collided by accident — belt and braces on
        # top of the independent-secret guarantee the admin-auth spec
        # actually requires.
        "aud": "govassist-admin",
    }
    return jwt.encode(payload, _secret_key(), algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> uuid.UUID | None:
    """Returns the admin id the token was issued for, or None for any
    invalid/expired/malformed/wrong-audience token — callers turn that
    into a 401, never an exception leaking token-format details."""
    try:
        payload = jwt.decode(
            token, _secret_key(), algorithms=[JWT_ALGORITHM], audience="govassist-admin"
        )
        return uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
