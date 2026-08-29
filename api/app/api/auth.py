"""Item 7: POST /auth/signup, POST /auth/signin.

Deliberately minimal per the request — no OAuth, no email verification,
no password reset. Both routes return the same `TokenOut` shape so the
mobile client's post-auth handling is identical either way.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import SigninRequest, SignupRequest, TokenOut
from app.auth.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models import User

router = APIRouter(prefix="/auth", tags=["auth"])

# Deliberately loose (format sanity, not full RFC 5322) — the only real
# validation that matters is "does signing in with this email/password
# actually work," which bcrypt verification already enforces.
_MIN_PASSWORD_LENGTH = 8


def _normalize_email(email: str) -> str:
    return email.strip().lower()


@router.post("/signup", response_model=TokenOut)
def signup(body: SignupRequest, db: Session = Depends(get_db)) -> TokenOut:
    email = _normalize_email(body.email)
    if "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(status_code=422, detail="Enter a valid email address")
    if len(body.password) < _MIN_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=422, detail=f"Password must be at least {_MIN_PASSWORD_LENGTH} characters"
        )

    existing = db.scalars(select(User).where(User.email == email)).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    user = User(email=email, password_hash=hash_password(body.password))
    db.add(user)
    db.commit()
    db.refresh(user)

    return TokenOut(access_token=create_access_token(user.id))


@router.post("/signin", response_model=TokenOut)
def signin(body: SigninRequest, db: Session = Depends(get_db)) -> TokenOut:
    email = _normalize_email(body.email)
    user = db.scalars(select(User).where(User.email == email)).first()

    # Same error for "no such account" and "wrong password" — never
    # reveal which one it was (standard practice, not stated in the
    # request but the obvious right default for an auth endpoint).
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    return TokenOut(access_token=create_access_token(user.id))
