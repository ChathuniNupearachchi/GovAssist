"""Top-level entry point: ties the condition evaluator, requirement
resolver, fee calculator, and office resolver together into one case
resolution, and implements the two behaviors that don't belong to any
single component — the under-16 scope gate (4.x SCOPE GATE) and the
amendment-alternative surfacing (AMENDMENT BRANCH).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.engine.fees import resolve_fee
from app.engine.offices import resolve_offices
from app.engine.requirements import resolve_requirements
from app.engine.types import AmendmentAlternative, CaseResolution, ScopeGateResponse
from app.models import RuleVersion, Service

RENEWAL_SERVICE_CODE = "passport-renewal"
AMENDMENT_SERVICE_CODE = "passport-amendment"
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
    amendment_rv = _approved_rule_version(db, AMENDMENT_SERVICE_CODE)
    fee = resolve_fee(db, amendment_rv.id, basis="normal")
    requirements = resolve_requirements(db, amendment_rv.id, answers={})
    return AmendmentAlternative(fee=fee, requirements=requirements)


def resolve_case(db: Session, answers: dict[str, str]) -> CaseResolution:
    """Resolve an adult passport renewal case.

    Age SHALL be evaluated first, unconditionally, before any other
    resolution runs — an under-16 answer short-circuits straight to the
    scope-gate response with no requirements, fee, offices, or plan.
    """
    if "age" not in answers:
        raise ValueError("resolve_case requires an 'age' answer before resolving")
    age = float(answers["age"])
    if age < 16:
        return CaseResolution(scope_gate=ScopeGateResponse(reason=SCOPE_GATE_UNDER_16))

    renewal_rv = _approved_rule_version(db, RENEWAL_SERVICE_CODE)
    requirements = resolve_requirements(db, renewal_rv.id, answers)
    fee = resolve_fee(db, renewal_rv.id, basis=answers.get("service_basis", "normal"))
    offices = resolve_offices(
        db,
        district=answers.get("district"),
        basis=answers.get("service_basis", "normal"),
    )

    amendment_alternative = None
    if answers.get("name_changed") == "true":
        amendment_alternative = _amendment_alternative(db)

    return CaseResolution(
        requirements=requirements,
        fee=fee,
        offices=offices,
        amendment_alternative=amendment_alternative,
    )
