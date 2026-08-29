"""admin-dashboard change, task 3.4 — `get_current_admin`, the FastAPI
dependency every admin route other than signup/signin requires. Mirrors
`api/app/auth/dependencies.py`'s `get_current_user` shape exactly, over
`AdminUser` and the admin token space instead."""

from __future__ import annotations

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.security import decode_access_token
from app.db.session import get_db
from app.models import AdminUser

_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> AdminUser:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing bearer token")

    admin_id = decode_access_token(credentials.credentials)
    if admin_id is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    admin = db.get(AdminUser, admin_id)
    if admin is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return admin
