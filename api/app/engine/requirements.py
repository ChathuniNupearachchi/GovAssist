"""4.2 Requirement resolver + 4.5 prerequisite ordering.

Prerequisite ordering is folded into the resolver rather than a separate
module (per tasks.md 12.1's "or fold into requirements.py") — sequence
is already the resolver's sort key, and the seed data's sequence numbers
already encode the required order (studio acknowledgement=1, fingerprints
=2, ... new-NIC=19, before the dual-citizen documents=20+), so no
separate ordering pass is needed on top of the resolver's own query.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.engine.conditions import condition_link_passes
from app.engine.types import Citation, ResolvedRequirement
from app.models import Requirement, RequirementCondition, RuleVersion


def _citation(db: Session, requirement: Requirement, rule_version: RuleVersion) -> Citation:
    """A requirement's own source_document_id, falling back to its rule
    version's, per the "resolve per rule version" spec's fallback rule."""
    doc = requirement.source_document or rule_version.source_document
    return Citation(
        source_document_id=doc.id,
        source_url=doc.source_url,
        verified_at=rule_version.verified_at,
    )


def resolve_requirements(
    db: Session, rule_version_id: uuid.UUID, answers: dict[str, str]
) -> list[ResolvedRequirement]:
    """Return the requirements whose gating conditions all pass, ordered
    by sequence. A requirement with no linked conditions is unconditional
    and always included (e.g. the photo studio acknowledgement)."""
    rule_version = db.get(RuleVersion, rule_version_id)
    requirements = db.scalars(
        select(Requirement)
        .where(Requirement.rule_version_id == rule_version_id)
        .order_by(Requirement.sequence)
    ).all()

    resolved: list[ResolvedRequirement] = []
    for requirement in requirements:
        links = db.scalars(
            select(RequirementCondition).where(
                RequirementCondition.requirement_id == requirement.id
            )
        ).all()
        if all(
            condition_link_passes(link.condition, link.negated, answers)
            for link in links
        ):
            resolved.append(
                ResolvedRequirement(
                    id=requirement.id,
                    label=requirement.label,
                    kind=requirement.kind,
                    sequence=requirement.sequence,
                    citation=_citation(db, requirement, rule_version),
                    resources=requirement.resources,
                )
            )
    return resolved
