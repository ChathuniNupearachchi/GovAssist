"""Item 7: POST /plans/save, GET /plans, DELETE /plans/{id} — every
route here requires a valid bearer token (`get_current_user`)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import SavePlanRequest, SavedPlanOut
from app.auth.dependencies import get_current_user
from app.db.session import get_db
from app.models import Case, SavedPlan, User

router = APIRouter(prefix="/plans", tags=["plans"])


@router.post("/save", response_model=SavedPlanOut)
def save_plan(
    body: SavePlanRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SavedPlanOut:
    case = db.get(Case, body.case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    if case.resolved_at is None:
        # A saved plan is a bookmark onto a computed plan — saving an
        # unresolved case would just re-raise the same 409 on reopen
        # (see `app.api.cases.resolve`), so reject it up front instead
        # of accepting a save that can never actually be reopened.
        raise HTTPException(status_code=400, detail="This case hasn't been resolved into a plan yet")

    label = body.label.strip()
    if not label:
        raise HTTPException(status_code=422, detail="Label can't be empty")

    saved_plan = SavedPlan(user_id=user.id, case_id=case.id, label=label)
    db.add(saved_plan)
    db.commit()
    db.refresh(saved_plan)

    return SavedPlanOut.from_model(saved_plan)


@router.get("", response_model=list[SavedPlanOut])
def list_plans(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[SavedPlanOut]:
    # A citizen may hold several plans at once (e.g. their own renewal
    # and a child's under-16 application) — most recent first, since
    # that's almost always the one they just came back to check.
    plans = db.scalars(
        select(SavedPlan).where(SavedPlan.user_id == user.id).order_by(SavedPlan.created_at.desc())
    ).all()
    return [SavedPlanOut.from_model(p) for p in plans]


@router.delete("/{plan_id}", status_code=204)
def delete_plan(
    plan_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    plan = db.get(SavedPlan, plan_id)
    # 404 for "doesn't exist" AND "exists but isn't yours" alike — never
    # confirm another user's plan id exists.
    if plan is None or plan.user_id != user.id:
        raise HTTPException(status_code=404, detail="Saved plan not found")

    db.delete(plan)
    db.commit()
