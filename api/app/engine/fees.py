"""4.3 Fee calculator.

`answers` (task: langgraph-orchestration-branch's tool-selection-
instability fix, generalized for lost/stolen's penalty tiers — Phase 9
service #3) lets a fee rule set express a conditional fee tier — e.g.
the renewal service's below-16 tier (LKR 3,000/9,000, source:
pages_e.php?id=8's "processing fees for All-Countries Passport (below
16 years of age)" table) versus the adult tier (LKR 10,000/20,000) for
the same `basis`, or `passport-lost-stolen`'s combined base-fee-plus-
penalty totals gated on how long ago the lost passport was issued
(`app.seed.phase9_lost_stolen`). Originally age-only (`get_fee` had no
way to select the below-16 tier at all, so an agent question about a
minor's fee could only ever surface the adult amount — confirmed as a
real gap by a golden-set scenario built specifically to surface it);
generalized from a single `age` value to the citizen's full `answers`
dict so a `FeeRule.condition_id` can gate on ANY attribute, not only
age — lost/stolen's penalty tiers need this. Conditional fee rules use
`FeeRule.condition_id` (already in the Phase 2 schema) linking to a
Condition the same way a Requirement or Question does — no new column.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.engine.conditions import evaluate_condition
from app.engine.types import Citation, ResolvedFee
from app.models import Condition, FeeRule, RuleVersion


def resolve_fee(
    db: Session, rule_version_id: uuid.UUID, basis: str, answers: dict[str, str] | None = None
) -> ResolvedFee | None:
    """Return the fee rule matching the rule version, basis (normal/
    urgent), and — when the rule set has more than one fee rule for that
    basis — the citizen's answers. A `FeeRule` with a linked `Condition`
    (e.g. age < 16, or lost/stolen's penalty-tier attribute) applies
    only when `answers` satisfies it; the unconditional `FeeRule` (no
    `condition_id`) is the default, used when `answers` is None/empty or
    no conditional rule matches. Candidates are evaluated in `id` order
    (insertion order for this project's own seed scripts) — the FIRST
    matching conditional rule wins, so a rule set relying on more than
    one simultaneously-matchable conditional tier for the same `basis`
    needs its own tie-break, not assumed here. Returns None if no
    matching fee rule exists at all."""
    rule_version = db.get(RuleVersion, rule_version_id)
    candidates = db.scalars(
        select(FeeRule).where(
            FeeRule.rule_version_id == rule_version_id, FeeRule.basis == basis
        )
    ).all()
    if not candidates:
        return None

    fee_rule = None
    if answers:
        for candidate in candidates:
            if candidate.condition_id is None:
                continue
            condition = db.get(Condition, candidate.condition_id)
            if condition is not None and evaluate_condition(condition, answers):
                fee_rule = candidate
                break
    if fee_rule is None:
        fee_rule = next((c for c in candidates if c.condition_id is None), None)
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
