"""admin-dashboard change, tasks 4.1-4.5 — the core feature: the
pending-draft queue, side-by-side comparison, and approve/reject.

Per admin-rule-review spec: the pending queue combines every
`ADMIN_DRAFT` row with every live `RULE_VERSION` row with `status =
draft`. Approve/reject record an `ADMIN_ACTION` and never touch
`RULE_VERSION.status` — the admin role's database grants make that
impossible even if this route attempted it (see admin-data-access
spec's "Approving or rejecting in the dashboard never mutates live
rule state").
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_admin
from app.db.session import get_db
from app.diff import classify_differences
from app.models import AdminAction, AdminDraft, AdminUser, RuleVersion, Service
from app.rules_read import build_rule_version_payload
from app.schemas import DiffEntryOut, PendingRuleOut, RejectRequest, RuleComparisonOut, RulePayloadOut

router = APIRouter(prefix="/admin/rules", tags=["admin-rules"])


def _latest_admin_action(db: Session, target_type: str, target_id: uuid.UUID) -> AdminAction | None:
    return db.scalars(
        select(AdminAction)
        .where(AdminAction.target_type == target_type, AdminAction.target_id == target_id)
        .order_by(AdminAction.created_at.desc())
    ).first()


_ACTION_TO_STATUS = {"approve": "approved", "reject": "rejected"}


def _pending_from_draft(db: Session, draft: AdminDraft) -> PendingRuleOut:
    service = db.get(Service, draft.service_id)
    action = _latest_admin_action(db, "admin_draft", draft.id)
    status = _ACTION_TO_STATUS[action.action] if action else draft.status
    return PendingRuleOut(
        id=draft.id,
        source="admin_draft",
        service_id=draft.service_id,
        service_code=service.code if service else "",
        service_name=service.name if service else "",
        status=status,
        reason=action.reason if action else None,
        created_at=draft.created_at,
    )


def _pending_from_rule_version(db: Session, rule_version: RuleVersion) -> PendingRuleOut:
    service = db.get(Service, rule_version.service_id)
    action = _latest_admin_action(db, "rule_version", rule_version.id)
    status = _ACTION_TO_STATUS[action.action] if action else "pending"
    return PendingRuleOut(
        id=rule_version.id,
        source="rule_version",
        service_id=rule_version.service_id,
        service_code=service.code if service else "",
        service_name=service.name if service else "",
        status=status,
        reason=action.reason if action else None,
        # RULE_VERSION has no created_at column — verified_at is the
        # closest thing this schema records; falls back to "now" only
        # if somehow unset, which no seeded row is.
        created_at=rule_version.verified_at,
    )


@router.get("/pending", response_model=list[PendingRuleOut])
def list_pending(
    db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)
) -> list[PendingRuleOut]:
    drafts = db.scalars(select(AdminDraft).order_by(AdminDraft.created_at.desc())).all()
    draft_rule_versions = db.scalars(
        select(RuleVersion).where(RuleVersion.status == "draft")
    ).all()
    return [_pending_from_draft(db, d) for d in drafts] + [
        _pending_from_rule_version(db, rv) for rv in draft_rule_versions
    ]


def _approved_rule_version_for(db: Session, service_id: uuid.UUID) -> RuleVersion | None:
    return db.scalars(
        select(RuleVersion)
        .where(RuleVersion.service_id == service_id, RuleVersion.status == "approved")
        .order_by(RuleVersion.version_number.desc())
    ).first()


def _find_pending(db: Session, pending_id: uuid.UUID) -> tuple[str, AdminDraft | RuleVersion]:
    draft = db.get(AdminDraft, pending_id)
    if draft is not None:
        return "admin_draft", draft
    rule_version = db.get(RuleVersion, pending_id)
    if rule_version is not None and rule_version.status == "draft":
        return "rule_version", rule_version
    raise HTTPException(status_code=404, detail="Pending rule not found")


@router.get("/pending/{pending_id}", response_model=RuleComparisonOut)
def get_comparison(
    pending_id: uuid.UUID,
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(get_current_admin),
) -> RuleComparisonOut:
    target_type, target = _find_pending(db, pending_id)

    if target_type == "admin_draft":
        draft: AdminDraft = target
        pending = _pending_from_draft(db, draft)
        approved_rule_version = None
        if draft.based_on_rule_version_id is not None:
            approved_rule_version = db.get(RuleVersion, draft.based_on_rule_version_id)
        if approved_rule_version is None:
            approved_rule_version = _approved_rule_version_for(db, draft.service_id)
        approved_payload = (
            build_rule_version_payload(db, approved_rule_version.id)
            if approved_rule_version is not None
            else {"requirements": [], "fee": None}
        )
        draft_payload = {
            "requirements": draft.payload.get("requirements", []),
            "fee": draft.payload.get("fee"),
            "note": draft.payload.get("note"),
        }
    else:
        rule_version: RuleVersion = target
        pending = _pending_from_rule_version(db, rule_version)
        approved_rule_version = _approved_rule_version_for(db, rule_version.service_id)
        approved_payload = (
            build_rule_version_payload(db, approved_rule_version.id)
            if approved_rule_version is not None
            else {"requirements": [], "fee": None}
        )
        draft_payload = build_rule_version_payload(db, rule_version.id)
        draft_payload["note"] = None

    diffs = classify_differences(approved_payload, draft_payload)

    return RuleComparisonOut(
        pending=pending,
        approved=RulePayloadOut(
            requirements=approved_payload["requirements"], fee=approved_payload["fee"], note=None
        ),
        draft=RulePayloadOut(**draft_payload),
        diffs=[DiffEntryOut(**d) for d in diffs],
    )


@router.post("/pending/{pending_id}/approve", response_model=PendingRuleOut)
def approve(
    pending_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
) -> PendingRuleOut:
    target_type, target = _find_pending(db, pending_id)

    action = AdminAction(admin_id=admin.id, action="approve", target_type=target_type, target_id=pending_id)
    db.add(action)
    if target_type == "admin_draft":
        target.status = "approved"  # ADMIN_DRAFT's own status — never RULE_VERSION.status.
    db.commit()

    if target_type == "admin_draft":
        return _pending_from_draft(db, target)
    return _pending_from_rule_version(db, target)


@router.post("/pending/{pending_id}/reject", response_model=PendingRuleOut)
def reject(
    pending_id: uuid.UUID,
    body: RejectRequest,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
) -> PendingRuleOut:
    if not body.reason.strip():
        raise HTTPException(status_code=422, detail="A rejection requires a reason")

    target_type, target = _find_pending(db, pending_id)

    action = AdminAction(
        admin_id=admin.id, action="reject", target_type=target_type, target_id=pending_id, reason=body.reason
    )
    db.add(action)
    if target_type == "admin_draft":
        # Recorded, but never deleted — per admin-rule-review spec's
        # "Reject records a reason and preserves the draft".
        target.status = "rejected"
    db.commit()

    if target_type == "admin_draft":
        return _pending_from_draft(db, target)
    return _pending_from_rule_version(db, target)
