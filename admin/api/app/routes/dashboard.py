"""admin-dashboard change, task 5.1 — GET /admin/dashboard/summary.

Operational status only, per design.md's explicit exclusion: no RAGAS
retrieval-quality panel, no Langfuse LLM-tracing panel — see
admin-dashboard-home spec's "No retrieval-quality or LLM-tracing views
on this dashboard" requirement. Both already have their own dedicated
interfaces suited to their own audience; neither tells a reviewer
whether a specific fee, document, or office is correct.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_admin
from app.db.session import get_db
from app.models import AdminAction, AdminDraft, AdminUser, RuleVersion, Service, SourceDocument
from app.schemas import DashboardSummaryOut, RecentApprovalOut

router = APIRouter(prefix="/admin/dashboard", tags=["admin-dashboard"])


@router.get("/summary", response_model=DashboardSummaryOut)
def summary(
    db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)
) -> DashboardSummaryOut:
    drafts_pending = db.scalar(
        select(func.count()).select_from(AdminDraft).where(AdminDraft.status == "pending")
    ) or 0
    drafts_pending += db.scalar(
        select(func.count()).select_from(RuleVersion).where(RuleVersion.status == "draft")
    ) or 0

    sources_pending = db.scalar(
        select(func.count()).select_from(SourceDocument).where(SourceDocument.status == "pending")
    ) or 0

    services_with_approved = set(
        db.scalars(
            select(RuleVersion.service_id).where(RuleVersion.status == "approved").distinct()
        ).all()
    )
    all_service_ids = set(db.scalars(select(Service.id)).all())
    services_without_approved_rule = len(all_service_ids - services_with_approved)

    recent_actions = db.execute(
        select(AdminAction, AdminUser.email)
        .join(AdminUser, AdminAction.admin_id == AdminUser.id)
        .order_by(AdminAction.created_at.desc())
        .limit(10)
    ).all()

    return DashboardSummaryOut(
        drafts_pending=drafts_pending,
        sources_pending=sources_pending,
        services_without_approved_rule=services_without_approved_rule,
        recently_approved=[
            RecentApprovalOut(
                id=action.id,
                action=action.action,
                target_type=action.target_type,
                target_id=action.target_id,
                reason=action.reason,
                admin_email=email,
                created_at=action.created_at,
            )
            for action, email in recent_actions
        ],
    )
