"""admin-dashboard change: builds a rule version's full, unconditional
requirement/fee payload for the rule-review comparison view.

Deliberately NOT a call into the citizen system's `app.engine.
requirements`/`app.engine.fees` resolvers (which return the subset that
applies to *one citizen's* answers) — a reviewer needs to see every
requirement and fee rule a rule version defines, not one citizen's
resolved plan, and reusing those functions across the package boundary
this change deliberately keeps separate (design.md: "Two fully separate
applications, sharing only the database") would need importing the
citizen system's `app` package, which collides with this package's own
name — see `app/models.py`'s docstring. The query here is a few lines
simpler than that reuse would be, so it's just written directly instead.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import FeeRule, Requirement, RuleVersion, SourceDocument


def _citation_dict(db: Session, source_document_id: uuid.UUID | None, rule_version: RuleVersion) -> dict:
    doc = db.get(SourceDocument, source_document_id) if source_document_id is not None else None
    if doc is None:
        doc = rule_version.source_document
    return {
        "source_document_id": str(doc.id),
        "source_url": doc.source_url,
        "verified_at": rule_version.verified_at.isoformat() if rule_version.verified_at else None,
    }


def build_rule_version_payload(db: Session, rule_version_id: uuid.UUID, basis: str = "normal") -> dict:
    """Returns `{"requirements": [...], "fee": {...} | None}` for every
    requirement defined on this rule version (unconditional — no
    citizen answers involved) plus its unconditional fee rule for
    `basis` (the one with no linked `Condition`, matching what the
    seeded draft's own fee represents)."""
    rule_version = db.get(RuleVersion, rule_version_id)
    if rule_version is None:
        return {"requirements": [], "fee": None}

    requirements = db.scalars(
        select(Requirement)
        .where(Requirement.rule_version_id == rule_version_id)
        .order_by(Requirement.sequence)
    ).all()
    requirement_dicts = [
        {
            "id": str(r.id),
            "label": r.label,
            "kind": r.kind,
            "sequence": r.sequence,
            "citation": _citation_dict(db, r.source_document_id, rule_version),
            "resources": r.resources,
        }
        for r in requirements
    ]

    fee_rules = db.scalars(
        select(FeeRule).where(
            FeeRule.rule_version_id == rule_version_id, FeeRule.basis == basis
        )
    ).all()
    fee_rule = next((f for f in fee_rules if f.condition_id is None), None) or (
        fee_rules[0] if fee_rules else None
    )
    fee_dict = None
    if fee_rule is not None:
        fee_dict = {
            "basis": fee_rule.basis,
            "base_amount": float(fee_rule.base_amount),
            "currency": fee_rule.currency,
            "penalty_amount": float(fee_rule.penalty_amount) if fee_rule.penalty_amount is not None else None,
            "citation": _citation_dict(db, fee_rule.source_document_id, rule_version),
        }

    return {"requirements": requirement_dicts, "fee": fee_dict}
