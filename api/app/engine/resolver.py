"""Top-level entry point: ties the condition evaluator, requirement
resolver, fee calculator, and office resolver together into one case
resolution, and implements the two behaviors that don't belong to any
single component — the under-16 scope gate (4.x SCOPE GATE), the
amendment-alternative surfacing (AMENDMENT BRANCH), and the intake-
completeness guard (see `IncompleteCaseError`).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.engine.fees import resolve_fee
from app.engine.next_question import next_question
from app.engine.offices import resolve_offices
from app.engine.requirements import resolve_requirements
from app.engine.types import (
    AmendmentAlternative,
    CaseResolution,
    IncompleteCaseError,
    ScopeGateResponse,
)
from app.models import RuleVersion, Service

RENEWAL_SERVICE_CODE = "passport-renewal"
AMENDMENT_SERVICE_CODE = "passport-amendment"
NEW_APPLICANT_SERVICE_CODE = "passport-new"
LOST_STOLEN_SERVICE_CODE = "passport-lost-stolen"
UNDER_16_SERVICE_CODE = "passport-under-16"
CHILD_DELETION_SERVICE_CODE = "passport-child-deletion"
EMERGENCY_CERTIFICATE_SERVICE_CODE = "emergency-certificate"
SCOPE_GATE_UNDER_16 = (
    "GovAssist does not yet support passport applications for applicants "
    "under 16. Under-16 applications have their own document set, "
    "consent requirements, and fee structure (validity-period dependent: "
    "LKR 3,000/9,000 for 3-year validity, LKR 10,000/20,000 for 10-year) "
    "that this build does not yet encode. Please contact the Department "
    "of Immigration and Emigration directly for a minor's application."
)


def _approved_rule_version(db: Session, service_code: str) -> RuleVersion:
    service = db.scalars(select(Service).where(Service.code == service_code)).first()
    if service is None:
        raise RuntimeError(f"Service '{service_code}' has not been seeded.")
    rule_version = db.scalars(
        select(RuleVersion).where(
            RuleVersion.service_id == service.id, RuleVersion.status == "approved"
        )
    ).first()
    if rule_version is None:
        raise RuntimeError(f"Service '{service_code}' has no approved rule version.")
    return rule_version


def _amendment_alternative(db: Session) -> AmendmentAlternative:
    """Surfaced only when `name_changed == "true"` (see `resolve_case`
    below) — the alternative being offered is specifically "amend your
    existing passport's name instead of renewing," so this always
    resolves the Change of Name alteration type. Phase 9's amendment
    implementation made every non-Change-of-Name Requirement
    conditional on `alteration_type` (see `app.seed.phase9_amendment`);
    passing this explicitly (rather than the previous `answers={}`)
    keeps this alternative's Requirement set from silently going empty
    now that Change of Name's own documents are gated too."""
    amendment_rv = _approved_rule_version(db, AMENDMENT_SERVICE_CODE)
    answers = {"alteration_type": "change_of_name"}
    fee = resolve_fee(db, amendment_rv.id, basis="normal", answers=answers)
    requirements = resolve_requirements(db, amendment_rv.id, answers=answers)
    return AmendmentAlternative(fee=fee, requirements=requirements)


def resolve_case(
    db: Session, answers: dict[str, str], service_code: str = RENEWAL_SERVICE_CODE
) -> CaseResolution:
    """Resolve a passport case for `service_code` — `passport-renewal`
    by default (every existing caller predates `passport-new`, so the
    default keeps them unchanged), or `passport-new` for a first-time
    applicant. Both services share this one function — design.md's
    service #2: "same documents/fee/form as renewal" (down to the same
    office/fee resolvers below), so there is no first-time-specific
    resolution logic here, only a different `service_code` selecting a
    different service's own seeded Questions/Requirements/FeeRules.

    Age SHALL be evaluated first, before any other resolution runs — an
    under-16 answer short-circuits straight to the scope-gate response
    with no requirements, fee, offices, or plan, UNLESS `service_code`
    IS `passport-under-16` (Phase 9 service #5) — that service's whole
    premise is a child under 16, so the gate that exists to refuse a
    minor's application everywhere else would refuse the one service
    built specifically to handle it.

    Every relevant question for `service_code` SHALL be answered before
    a requirement set is produced — raises `IncompleteCaseError`
    otherwise rather than returning a `CaseResolution` built from
    partial answers. A missing answer makes `condition_link_passes` fail
    *every* gating condition it appears in, regardless of negation, so
    an incomplete `answers` dict does not mean "everything not yet known
    to apply" — it can silently suppress both sides of a branch at once
    (see `IncompleteCaseError`'s docstring). Checked with the same
    `next_question` this case's own intake already uses to decide
    whether it's done, so there is exactly one definition of "complete",
    not a second one duplicated here.
    """
    if "age" not in answers:
        raise ValueError("resolve_case requires an 'age' answer before resolving")
    age = float(answers["age"])
    if age < 16 and service_code != UNDER_16_SERVICE_CODE:
        return CaseResolution(scope_gate=ScopeGateResponse(reason=SCOPE_GATE_UNDER_16))

    service = db.scalars(select(Service).where(Service.code == service_code)).first()
    if service is None:
        raise RuntimeError(f"Service '{service_code}' has not been seeded.")
    pending = next_question(db, service.id, answers)
    if pending is not None:
        raise IncompleteCaseError(pending.prompt)

    rule_version = _approved_rule_version(db, service_code)
    requirements = resolve_requirements(db, rule_version.id, answers)
    fee = resolve_fee(db, rule_version.id, basis=answers.get("service_basis", "normal"), answers=answers)
    offices = resolve_offices(
        db,
        district=answers.get("district"),
        basis=answers.get("service_basis", "normal"),
        applying_from=answers.get("applying_from"),
    )

    # Amendment is offered as a same-request alternative only for a
    # citizen already renewing — a first-time applicant has no existing
    # passport to amend, so there is nothing to compare against
    # regardless of whether name_changed is true (design.md: "different
    # citizen framing," not a shared amendment-alternative concept).
    amendment_alternative = None
    if service_code == RENEWAL_SERVICE_CODE and answers.get("name_changed") == "true":
        amendment_alternative = _amendment_alternative(db)

    return CaseResolution(
        requirements=requirements,
        fee=fee,
        offices=offices,
        amendment_alternative=amendment_alternative,
    )
