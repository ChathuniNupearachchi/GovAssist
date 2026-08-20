"""6.3 GET /services."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import ServiceOut
from app.db.session import get_db
from app.models import Service

router = APIRouter(tags=["services"])


@router.get("/services", response_model=list[ServiceOut])
def list_services(db: Session = Depends(get_db)) -> list[ServiceOut]:
    services = db.scalars(select(Service).order_by(Service.name)).all()
    return [
        ServiceOut(id=s.id, code=s.code, name=s.name, category=s.category)
        for s in services
    ]
