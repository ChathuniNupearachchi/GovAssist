"""Phase 7 (mobile-app-integration): GET /studios.

The one backend addition this phase makes — a scoped, explicit
exception to "no backend changes" (see phase-7-mobile-app-integration's
design.md). Wraps `app.engine.studios.resolve_studios`, which already
existed (seeded from Phase 9's studio scraper) but had no route calling
it. No other route, schema, or engine function changes.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import StudioResolutionOut
from app.chat.deterministic import DISTRICTS
from app.db.session import get_db
from app.engine.studios import resolve_studios

router = APIRouter(tags=["studios"])


@router.get("/studios", response_model=StudioResolutionOut)
def get_studios(district: str, db: Session = Depends(get_db)) -> StudioResolutionOut:
    if district not in DISTRICTS:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown district {district!r} — expected one of the 25 Sri Lankan districts.",
        )
    resolution = resolve_studios(db, district)
    return StudioResolutionOut.from_resolved(resolution)
