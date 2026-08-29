"""admin-dashboard change, task 8.1 — GET /admin/plans/audit.

Per admin-plan-audit spec: reads real, live saved `CASE` rows and flags
a case as outdated when its resolved rule version has since been
superseded by a newer approved version for the same service — computed
here only, never written back to `CASE.outdated` or any other live
column (the admin role couldn't write it even if this route tried).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_admin
from app.db.session import get_db
from app.models import AdminUser, Case, PlanItem, RuleVersion, Service
from app.schemas import PlanAuditOut

router = APIRouter(prefix="/admin/plans", tags=["admin-plans"])


@router.get("/audit", response_model=list[PlanAuditOut])
def plan_audit(
    db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)
) -> list[PlanAuditOut]:
    cases = db.scalars(
        select(Case).where(Case.resolved_at.is_not(None)).order_by(Case.resolved_at.desc())
    ).all()

    results: list[PlanAuditOut] = []
    for case in cases:
        # A resolved case's rule version — the version its PLAN_ITEM
        # rows were actually built against; any one of them names it,
        # since a case resolves against exactly one rule version at a
        # time.
        plan_item = db.scalars(
            select(PlanItem).where(PlanItem.case_id == case.id).limit(1)
        ).first()
        if plan_item is None:
            continue
        resolved_rule_version = db.get(RuleVersion, plan_item.rule_version_id)
        if resolved_rule_version is None:
            continue

        current_approved = db.scalars(
            select(RuleVersion)
            .where(RuleVersion.service_id == case.service_id, RuleVersion.status == "approved")
            .order_by(RuleVersion.version_number.desc())
        ).first()

        outdated = (
            current_approved is not None and current_approved.id != resolved_rule_version.id
        )

        service = db.get(Service, case.service_id)
        results.append(
            PlanAuditOut(
                case_id=case.id,
                service_code=service.code if service else "",
                service_name=service.name if service else "",
                resolved_at=case.resolved_at,
                resolved_rule_version_number=resolved_rule_version.version_number,
                resolved_rule_version_status=resolved_rule_version.status,
                current_approved_rule_version_number=(
                    current_approved.version_number if current_approved else None
                ),
                outdated=outdated,
            )
        )

    return results
