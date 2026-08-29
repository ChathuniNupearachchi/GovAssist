"""admin-dashboard change, tasks 6.1-6.4 — GET /admin/services, GET
/admin/services/{id}, and overlay-only create/update/delete.

Per admin-service-catalog spec's "Hand-verified rules display as
approved": a service's current rule version is whatever live
`RULE_VERSION` row has `status = approved` for it (the highest
`version_number` among those, since a service could in principle have
more than one historical approved version) — every rule version this
project has seeded to date was hand-verified against its source pages
during development, which is exactly what a reviewer does, so it is
shown as approved, never pending.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_admin
from app.db.session import get_db
from app.models import (
    AdminOverlay,
    AdminUser,
    Condition,
    FeeRule,
    Office,
    Question,
    Requirement,
    RequirementCondition,
    RuleVersion,
    Service,
    SourceDocument,
)
from app.schemas import (
    ConditionOut,
    FeeRuleOut,
    OverlayIn,
    OverlayOut,
    QuestionDetailOut,
    RequirementDetailOut,
    ResourceOut,
    ServiceDetailOut,
    ServiceSummaryOut,
)

router = APIRouter(prefix="/admin/services", tags=["admin-services"])


def _citation_out(db: Session, source_document_id: uuid.UUID | None, rule_version: RuleVersion) -> dict:
    doc = db.get(SourceDocument, source_document_id) if source_document_id is not None else None
    if doc is None:
        doc = rule_version.source_document
    return {
        "source_document_id": doc.id,
        "source_url": doc.source_url,
        "verified_at": rule_version.verified_at,
    }


def _current_rule_version(db: Session, service_id: uuid.UUID) -> RuleVersion | None:
    """The service's current rule version — the highest-numbered
    `approved` one when any exists, otherwise the highest-numbered row
    at all (so a service with only a draft still has something to
    drill into)."""
    approved = db.scalars(
        select(RuleVersion)
        .where(RuleVersion.service_id == service_id, RuleVersion.status == "approved")
        .order_by(RuleVersion.version_number.desc())
    ).first()
    if approved is not None:
        return approved
    return db.scalars(
        select(RuleVersion)
        .where(RuleVersion.service_id == service_id)
        .order_by(RuleVersion.version_number.desc())
    ).first()


def _summary(db: Session, service: Service) -> ServiceSummaryOut:
    rule_version = _current_rule_version(db, service.id)

    requirement_count = 0
    condition_count = 0
    if rule_version is not None:
        requirement_count = db.scalar(
            select(func.count()).select_from(Requirement).where(Requirement.rule_version_id == rule_version.id)
        ) or 0

    question_count = db.scalar(
        select(func.count()).select_from(Question).where(Question.service_id == service.id)
    ) or 0
    question_ids = db.scalars(select(Question.id).where(Question.service_id == service.id)).all()
    if question_ids:
        condition_count = db.scalar(
            select(func.count()).select_from(Condition).where(Condition.question_id.in_(question_ids))
        ) or 0

    return ServiceSummaryOut(
        id=service.id,
        code=service.code,
        name=service.name,
        category=service.category,
        requirement_count=requirement_count,
        condition_count=condition_count,
        question_count=question_count,
        current_rule_version_number=rule_version.version_number if rule_version else None,
        current_rule_version_status=rule_version.status if rule_version else None,
        last_verified_at=rule_version.verified_at if rule_version else None,
    )


@router.get("", response_model=list[ServiceSummaryOut])
def list_services(
    db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)
) -> list[ServiceSummaryOut]:
    services = db.scalars(select(Service).order_by(Service.name)).all()
    return [_summary(db, s) for s in services]


@router.get("/{service_id}", response_model=ServiceDetailOut)
def get_service(
    service_id: uuid.UUID,
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(get_current_admin),
) -> ServiceDetailOut:
    service = db.get(Service, service_id)
    if service is None:
        raise HTTPException(status_code=404, detail="Service not found")

    summary = _summary(db, service)
    rule_version = _current_rule_version(db, service.id)

    requirements: list[RequirementDetailOut] = []
    fee_rules: list[FeeRuleOut] = []
    if rule_version is not None:
        for r in db.scalars(
            select(Requirement)
            .where(Requirement.rule_version_id == rule_version.id)
            .order_by(Requirement.sequence)
        ).all():
            requirements.append(
                RequirementDetailOut(
                    id=r.id,
                    label=r.label,
                    kind=r.kind,
                    sequence=r.sequence,
                    freshness_rule=r.freshness_rule,
                    citation=_citation_out(db, r.source_document_id, rule_version),
                    resources=[ResourceOut(**res) for res in (r.resources or [])],
                )
            )
        for f in db.scalars(select(FeeRule).where(FeeRule.rule_version_id == rule_version.id)).all():
            fee_rules.append(
                FeeRuleOut(
                    id=f.id,
                    basis=f.basis,
                    base_amount=float(f.base_amount),
                    currency=f.currency,
                    penalty_amount=float(f.penalty_amount) if f.penalty_amount is not None else None,
                    condition_id=f.condition_id,
                    citation=_citation_out(db, f.source_document_id, rule_version),
                )
            )

    questions = db.scalars(
        select(Question).where(Question.service_id == service.id).order_by(Question.sequence)
    ).all()
    question_out = [
        QuestionDetailOut(
            id=q.id, prompt=q.prompt, answer_type=q.answer_type, sequence=q.sequence, hint=q.hint
        )
        for q in questions
    ]

    conditions: list[ConditionOut] = []
    for q in questions:
        for c in db.scalars(select(Condition).where(Condition.question_id == q.id)).all():
            conditions.append(
                ConditionOut(id=c.id, question_id=c.question_id, attribute=c.attribute, operator=c.operator, value=c.value)
            )

    overlays = db.scalars(
        select(AdminOverlay)
        .where(AdminOverlay.target_type == "service", AdminOverlay.target_id == service.id)
        .order_by(AdminOverlay.created_at.desc())
    ).all()
    # Overlay-only creates (a brand-new service the dashboard proposes)
    # have no live target_id — they never appear under an existing
    # service's drill-down, only in a future "proposed services" list.

    return ServiceDetailOut(
        **summary.model_dump(),
        requirements=requirements,
        conditions=conditions,
        fee_rules=fee_rules,
        questions=question_out,
        overlays=[
            OverlayOut(
                id=o.id, target_type=o.target_type, target_id=o.target_id,
                operation=o.operation, payload=o.payload, created_at=o.created_at,
            )
            for o in overlays
        ],
    )


@router.post("/{service_id}/overlay", response_model=OverlayOut, status_code=201)
def write_service_overlay(
    service_id: uuid.UUID,
    body: OverlayIn,
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(get_current_admin),
) -> OverlayOut:
    """Create/update/delete on a service, recorded ONLY as an
    `ADMIN_OVERLAY` row — per admin-service-catalog spec's "Catalog
    edits are overlay-only", no live `SERVICE`/`RULE_VERSION`/
    `REQUIREMENT`/`CONDITION`/`FEE_RULE` row is ever touched (the
    admin role's database-level grants make a live write to any of
    those tables impossible even if this route attempted one)."""
    if body.operation != "create" and db.get(Service, service_id) is None:
        raise HTTPException(status_code=404, detail="Service not found")

    overlay = AdminOverlay(
        target_type="service",
        target_id=service_id if body.operation != "create" else body.target_id,
        operation=body.operation,
        payload=body.payload,
    )
    db.add(overlay)
    db.commit()
    db.refresh(overlay)

    return OverlayOut(
        id=overlay.id, target_type=overlay.target_type, target_id=overlay.target_id,
        operation=overlay.operation, payload=overlay.payload, created_at=overlay.created_at,
    )
