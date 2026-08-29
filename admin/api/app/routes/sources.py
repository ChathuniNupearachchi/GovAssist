"""admin-dashboard change, tasks 7.2-7.3 — GET /admin/sources, POST
/admin/sources/overlay."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_admin
from app.db.session import get_db
from app.extraction import extraction_method
from app.models import AdminOverlay, AdminUser, FeeRule, Requirement, RuleVersion, Service, SourceDocument
from app.schemas import OverlayOut, SourceOut, SourceOverlayIn

router = APIRouter(prefix="/admin/sources", tags=["admin-sources"])


def _supported_service_codes(db: Session, doc: SourceDocument) -> list[str]:
    service_ids: set = set()
    service_ids.update(
        db.scalars(select(RuleVersion.service_id).where(RuleVersion.source_document_id == doc.id)).all()
    )
    rule_version_ids_via_requirement = db.scalars(
        select(Requirement.rule_version_id).where(Requirement.source_document_id == doc.id)
    ).all()
    rule_version_ids_via_fee = db.scalars(
        select(FeeRule.rule_version_id).where(FeeRule.source_document_id == doc.id)
    ).all()
    other_rule_version_ids = set(rule_version_ids_via_requirement) | set(rule_version_ids_via_fee)
    if other_rule_version_ids:
        service_ids.update(
            db.scalars(select(RuleVersion.service_id).where(RuleVersion.id.in_(other_rule_version_ids))).all()
        )
    if not service_ids:
        return []
    codes = db.scalars(select(Service.code).where(Service.id.in_(service_ids)).order_by(Service.code)).all()
    return list(codes)


@router.get("", response_model=list[SourceOut])
def list_sources(
    db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)
) -> list[SourceOut]:
    documents = db.scalars(select(SourceDocument).order_by(SourceDocument.fetched_at.desc())).all()
    return [
        SourceOut(
            id=doc.id,
            source_url=doc.source_url,
            document_type=doc.document_type,
            status=doc.status,
            fetched_at=doc.fetched_at,
            approved_at=doc.approved_at,
            content_hash=doc.content_hash,
            extraction_method=extraction_method(doc.content_hash, doc.document_type),
            supported_services=_supported_service_codes(db, doc),
        )
        for doc in documents
    ]


@router.post("/overlay", response_model=OverlayOut, status_code=201)
def add_source_overlay(
    body: SourceOverlayIn,
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(get_current_admin),
) -> OverlayOut:
    """Records the intent to add a source as an `ADMIN_OVERLAY` row —
    per admin-source-catalog spec's "Adding a source records intent
    without live ingestion", this NEVER triggers the live scraper, PDF
    extraction, chunking, or embedding pipeline, and no live
    `SOURCE_DOCUMENT`/`DOCUMENT_CHUNK` row is created. The frontend is
    responsible for showing the resulting overlay as pending with a
    visible "not yet ingested" note (task 7.4) — this route's job is
    only to record the intent."""
    overlay = AdminOverlay(
        target_type="source_document",
        target_id=None,  # A brand-new source has no live id to point at.
        operation="create",
        payload={"source_url": body.source_url, "document_type": body.document_type},
    )
    db.add(overlay)
    db.commit()
    db.refresh(overlay)

    return OverlayOut(
        id=overlay.id, target_type=overlay.target_type, target_id=overlay.target_id,
        operation=overlay.operation, payload=overlay.payload, created_at=overlay.created_at,
    )
