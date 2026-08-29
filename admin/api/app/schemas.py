"""admin-dashboard change: Pydantic request/response models for
`/admin/api`. Field shapes mirror `api/app/api/schemas.py`'s own
`CitationOut`/`RequirementOut`/`FeeOut` conventions where the same data
is shown, so a reviewer sees the same citation shape a citizen's plan
does.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel


# --- Auth ---------------------------------------------------------------


class SignupRequest(BaseModel):
    email: str
    password: str
    role: Literal["reviewer", "approver"] = "reviewer"


class SigninRequest(BaseModel):
    email: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AdminUserOut(BaseModel):
    id: uuid.UUID
    email: str
    role: str


# --- Shared shapes --------------------------------------------------------


class CitationOut(BaseModel):
    source_document_id: uuid.UUID
    source_url: str
    verified_at: datetime | None


class ResourceOut(BaseModel):
    label: str
    url: str
    type: str


class RequirementDetailOut(BaseModel):
    id: uuid.UUID
    label: str
    kind: str
    sequence: int
    freshness_rule: str | None
    citation: CitationOut
    resources: list[ResourceOut] = []


class ConditionOut(BaseModel):
    id: uuid.UUID
    question_id: uuid.UUID
    attribute: str
    operator: str
    value: str


class FeeRuleOut(BaseModel):
    id: uuid.UUID
    basis: str
    base_amount: float
    currency: str
    penalty_amount: float | None
    condition_id: uuid.UUID | None
    citation: CitationOut


class QuestionDetailOut(BaseModel):
    id: uuid.UUID
    prompt: str
    answer_type: str
    sequence: int
    hint: str | None


# --- Dashboard home -------------------------------------------------------


class RecentApprovalOut(BaseModel):
    id: uuid.UUID
    action: str
    target_type: str
    target_id: uuid.UUID
    reason: str | None
    admin_email: str
    created_at: datetime


class DashboardSummaryOut(BaseModel):
    drafts_pending: int
    sources_pending: int
    services_without_approved_rule: int
    recently_approved: list[RecentApprovalOut]


# --- Overlays (shared by service and source catalogs) -----------------------


class OverlayIn(BaseModel):
    operation: Literal["create", "update", "delete"]
    target_id: uuid.UUID | None = None
    payload: dict[str, Any] = {}


class OverlayOut(BaseModel):
    id: uuid.UUID
    target_type: str
    target_id: uuid.UUID | None
    operation: str
    payload: dict[str, Any]
    created_at: datetime


# --- Service catalog --------------------------------------------------------


class ServiceSummaryOut(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    category: str
    requirement_count: int
    condition_count: int
    question_count: int
    current_rule_version_number: int | None
    current_rule_version_status: str | None
    last_verified_at: datetime | None


class ServiceDetailOut(ServiceSummaryOut):
    requirements: list[RequirementDetailOut]
    conditions: list[ConditionOut]
    fee_rules: list[FeeRuleOut]
    questions: list[QuestionDetailOut]
    overlays: list[OverlayOut] = []


# --- Source catalog ---------------------------------------------------------


class SourceOut(BaseModel):
    id: uuid.UUID
    source_url: str
    document_type: str
    status: str
    fetched_at: datetime
    approved_at: datetime | None
    content_hash: str
    extraction_method: str | None
    supported_services: list[str]


class SourceOverlayIn(BaseModel):
    source_url: str
    document_type: Literal["html", "pdf"] = "html"


# --- Rule review ------------------------------------------------------------


class PendingRuleOut(BaseModel):
    id: uuid.UUID
    source: Literal["admin_draft", "rule_version"]
    service_id: uuid.UUID
    service_code: str
    service_name: str
    status: str
    reason: str | None = None
    created_at: datetime | None


class RulePayloadOut(BaseModel):
    requirements: list[dict[str, Any]]
    fee: dict[str, Any] | None
    note: str | None = None


class DiffEntryOut(BaseModel):
    field: str
    approved_value: Any
    draft_value: Any
    materiality: Literal["material", "cosmetic"]


class RuleComparisonOut(BaseModel):
    pending: PendingRuleOut
    approved: RulePayloadOut
    draft: RulePayloadOut
    diffs: list[DiffEntryOut]


class RejectRequest(BaseModel):
    reason: str


# --- Plan audit ---------------------------------------------------------


class PlanAuditOut(BaseModel):
    case_id: uuid.UUID
    service_code: str
    service_name: str
    resolved_at: datetime
    resolved_rule_version_number: int
    resolved_rule_version_status: str
    current_approved_rule_version_number: int | None
    outdated: bool
