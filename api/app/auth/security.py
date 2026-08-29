"""Item 7 (user accounts): password hashing and JWT issuance/verification.

Deliberately minimal, per the request: no OAuth, no email verification,
no password reset. Password hashing via `bcrypt` directly (not
`passlib`, which has had bcrypt-backend compatibility issues with
recent bcrypt releases) — never store or log a plaintext password.
JWTs are stateless bearer tokens (`PyJWT`, HS256, signed with
`JWT_SECRET_KEY`); there is no server-side session/refresh-token store
in this minimal version, matching the "keep it simple" instruction —
a token is valid until it expires, full stop.
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
JWT_EXPIRES_MINUTES = 60 * 24 * 30  # 30 days — a citizen shouldn't be signed out mid-use of a mobile app.


def _secret_key() -> str:
    key = os.environ.get("JWT_SECRET_KEY")
    if not key:
        raise RuntimeError(
            "JWT_SECRET_KEY is not set — required for /auth/signup and /auth/signin. "
            "Set it in .env (see .env's own comment for item 7)."
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


def create_access_token(user_id: uuid.UUID) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=JWT_EXPIRES_MINUTES),
    }
    return jwt.encode(payload, _secret_key(), algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> uuid.UUID | None:
    """Returns the user id the token was issued for, or None for any
    invalid/expired/malformed token — callers turn that into a 401,
    never an exception leaking token-format details to the client."""
    try:
        payload = jwt.decode(token, _secret_key(), algorithms=[JWT_ALGORITHM])
        return uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
