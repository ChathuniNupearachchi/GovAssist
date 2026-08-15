"""4.3 Fee calculator."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.engine.types import Citation, ResolvedFee
from app.models import FeeRule, RuleVersion


def resolve_fee(db: Session, rule_version_id: uuid.UUID, basis: str) -> ResolvedFee | None:
    """Return the fee rule matching the rule version and basis
    (normal/urgent), or None if no such fee rule exists."""
    rule_version = db.get(RuleVersion, rule_version_id)
    fee_rule = db.scalars(
        select(FeeRule).where(
            FeeRule.rule_version_id == rule_version_id, FeeRule.basis == basis
        )
    ).first()
    if fee_rule is None:
        return None

    doc = fee_rule.source_document or rule_version.source_document
    return ResolvedFee(
        basis=fee_rule.basis,
        base_amount=float(fee_rule.base_amount),
        citation=Citation(
            source_document_id=doc.id,
            source_url=doc.source_url,
            verified_at=rule_version.verified_at,
        ),
    )
