"""admin-dashboard change, tasks 3.2-3.3 — POST /admin/auth/signup,
POST /admin/auth/signin. Mirrors `api/app/api/auth.py`'s shape, over
`AdminUser` and the admin token space instead."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models import AdminUser
from app.schemas import SigninRequest, SignupRequest, TokenOut

router = APIRouter(prefix="/admin/auth", tags=["admin-auth"])

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

    existing = db.scalars(select(AdminUser).where(AdminUser.email == email)).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    admin = AdminUser(email=email, role=body.role, password_hash=hash_password(body.password))
    db.add(admin)
    db.commit()
    db.refresh(admin)

    return TokenOut(access_token=create_access_token(admin.id))


@router.post("/signin", response_model=TokenOut)
def signin(body: SigninRequest, db: Session = Depends(get_db)) -> TokenOut:
    email = _normalize_email(body.email)
    admin = db.scalars(select(AdminUser).where(AdminUser.email == email)).first()

    # Same error for "no such account" and "wrong password" alike — never
    # reveal which one it was.
    if admin is None or not admin.password_hash or not verify_password(body.password, admin.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    return TokenOut(access_token=create_access_token(admin.id))
