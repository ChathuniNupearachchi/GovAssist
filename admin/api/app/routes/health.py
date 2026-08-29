"""admin-dashboard change, task 2.3 — liveness route."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/admin/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
