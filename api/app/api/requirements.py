"""6.3 GET /requirements/{id}."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import CitationOut, RequirementOut, ResourceOut
from app.db.session import get_db
from app.models import Requirement

router = APIRouter(tags=["requirements"])


@router.get("/requirements/{requirement_id}", response_model=RequirementOut)
def get_requirement(
    requirement_id: uuid.UUID, db: Session = Depends(get_db)
) -> RequirementOut:
    requirement = db.get(Requirement, requirement_id)
    if requirement is None:
        raise HTTPException(status_code=404, detail="Requirement not found")

    # Requirement's own citation, falling back to its rule version's —
    # same rule as app.engine.requirements._citation.
    doc = requirement.source_document or requirement.rule_version.source_document
    citation = CitationOut(
        source_document_id=doc.id,
        source_url=doc.source_url,
        verified_at=requirement.rule_version.verified_at,
    )
    return RequirementOut(
        id=requirement.id,
        label=requirement.label,
        kind=requirement.kind,
        sequence=requirement.sequence,
        citation=citation,
        resources=[ResourceOut(**res) for res in (requirement.resources or [])],
    )
