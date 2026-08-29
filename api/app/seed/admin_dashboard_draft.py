"""admin-dashboard change, task 1.7 — seeds the one demonstration
`ADMIN_DRAFT`: a renewal fee change from LKR 10,000 to LKR 12,000 (per
admin-rule-review spec's "Seeded demonstration draft" requirement),
so the comparison view has a genuine material difference to show
without the not-yet-built LLM rule-parsing pipeline (BACKEND_PLAN.md
3.5) needing to run.

`payload` is built directly from the live, currently-approved renewal
rule version's own requirements and fee (via the same
`resolve_requirements`/`resolve_fee` functions the citizen-facing
engine uses), with only the normal-basis fee's `base_amount` changed —
so the draft's shape matches exactly what a real future draft-producer
would need to emit (design.md's "The four admin-owned tables").

Idempotent: re-running this script replaces the one seeded draft rather
than accumulating duplicates.

Run with:  python -m app.seed.admin_dashboard_draft
"""

import dataclasses

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.engine.fees import resolve_fee
from app.engine.requirements import resolve_requirements
from app.engine.types import Citation, ResolvedFee, ResolvedRequirement
from app.models import AdminDraft, RuleVersion, Service

RENEWAL_CODE = "passport-renewal"
DRAFT_FEE_BASE_AMOUNT = 12000.00


def _citation_dict(c: Citation) -> dict:
    return {
        "source_document_id": str(c.source_document_id),
        "source_url": c.source_url,
        "verified_at": c.verified_at.isoformat() if c.verified_at else None,
    }


def _requirement_dict(r: ResolvedRequirement) -> dict:
    return {
        "id": str(r.id),
        "label": r.label,
        "kind": r.kind,
        "sequence": r.sequence,
        "citation": _citation_dict(r.citation),
        "resources": r.resources,
    }


def _fee_dict(f: ResolvedFee) -> dict:
    return {
        "basis": f.basis,
        "base_amount": f.base_amount,
        "currency": f.currency,
        "penalty_amount": f.penalty_amount,
        "citation": _citation_dict(f.citation),
    }


def seed(db: Session) -> None:
    service = db.scalars(select(Service).where(Service.code == RENEWAL_CODE)).first()
    if service is None:
        raise RuntimeError(f"Service '{RENEWAL_CODE}' has not been seeded — run app.seed.phase4_renewal first.")

    rule_version = db.scalars(
        select(RuleVersion).where(
            RuleVersion.service_id == service.id, RuleVersion.status == "approved"
        )
    ).first()
    if rule_version is None:
        raise RuntimeError(f"No approved rule version for '{RENEWAL_CODE}' — seed renewal first.")

    # A representative adult, domestic, no-special-condition answer set —
    # the draft's requirement set doesn't change, only its fee, so any
    # answer set that resolves the standard document set is fine here.
    answers = {
        "age": "30",
        "applying_from": "sri_lanka",
        "name_changed": "false",
        "dual_citizen": "false",
        "section_19_2": "false",
        "profession": "",
        "buddhist_priest": "false",
        "holds_passport": "true",
    }

    requirements = resolve_requirements(db, rule_version.id, answers)
    approved_fee = resolve_fee(db, rule_version.id, basis="normal", answers=answers)
    if approved_fee is None:
        raise RuntimeError("Could not resolve the current renewal fee to build the draft from.")

    draft_fee = dataclasses.replace(approved_fee, base_amount=DRAFT_FEE_BASE_AMOUNT)

    payload = {
        "requirements": [_requirement_dict(r) for r in requirements],
        "fee": _fee_dict(draft_fee),
        "note": (
            f"Proposed renewal fee change: LKR {approved_fee.base_amount:,.2f} "
            f"→ LKR {draft_fee.base_amount:,.2f} (normal basis). Requirements "
            "unchanged from the currently-approved version."
        ),
    }

    db.execute(delete(AdminDraft).where(AdminDraft.service_id == service.id))
    db.add(
        AdminDraft(
            service_id=service.id,
            based_on_rule_version_id=rule_version.id,
            payload=payload,
            status="pending",
        )
    )
    db.commit()


def main() -> None:
    db = SessionLocal()
    try:
        seed(db)
        print("Admin dashboard demonstration draft (renewal fee LKR 10,000 -> LKR 12,000) seeded.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
