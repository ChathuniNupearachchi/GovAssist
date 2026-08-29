"""Phase 9 seed data: Amend an Existing Passport service — design.md's
service #4.

Replaces the old `phase4_renewal.py` amendment stub (Change of Name
only, 2 unconditional Requirements, no offices, not independently
routable) with a full service covering all 6 of `id=10`'s alteration
types EXCEPT "Deletion of a child's name" (design.md's Round 2
correction: that's its own service — `passport-child-deletion` — with
its own form, per Conflict 3's evidence; not this one).

Unlike renewal/new-applicant/lost-stolen, amendment has no domestic-vs-
overseas FORM split: `id=10`'s own text lists "Overseas Sri Lankan
Missions" as just one of several places to obtain/submit the SAME
Alteration Application Form (`amendment.pdf`, "Form O") — not a
different PDF the way K-35A has a separate Overseas Missions variant.
So `applying_from` here only routes to a different set of OFFICES
(Mission-only when abroad, Head/Regional when domestic — the same
`resolve_offices` mechanism every other service already uses), not a
different form Requirement.

Also no `service_basis` (normal/urgent) — `id=10` states a single flat
fee (LKR 1,200) and a single delivery time (1h30m), no urgent tier, for
every alteration type.

Each alteration type's own documents are gated on `alteration_type` —
"Other Amendments" has NO documents specified in `id=10`'s own table
(a genuine gap, not filled in); modeled as an explicit prerequisite
naming the gap rather than silently showing no documents at all, so a
citizen picking "other" isn't left thinking nothing is required.

Run with:  python -m app.seed.phase9_amendment
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.engine.renewal_intake import AMENDMENT_QUESTIONS
from app.models import (
    Condition,
    FeeRule,
    Question,
    QuestionCondition,
    Requirement,
    RequirementCondition,
    RuleVersion,
    Service,
    SourceDocument,
)

AMENDMENT_CODE = "passport-amendment"

ALTERATION_TYPES = (
    "change_of_name",
    "profession_inclusion",
    "nic_inclusion",
    "cancel_single_journey",
    "cancel_india_nepal",
    "other",
)

EXPECTED_ATTRIBUTES = {
    "applying_from",
    "alteration_type",
}


def _source_document(db: Session, url_substring: str) -> SourceDocument:
    doc = db.scalars(
        select(SourceDocument)
        .where(SourceDocument.source_url.like(f"%{url_substring}"))
        .order_by(SourceDocument.fetched_at.asc())
    ).first()
    if doc is None:
        raise RuntimeError(
            f"No ingested SourceDocument found for '{url_substring}' — "
            "run the relevant scraper/ingestion script first."
        )
    return doc


def _wipe_existing(db: Session) -> None:
    service = db.scalars(select(Service).where(Service.code == AMENDMENT_CODE)).first()
    if service is None:
        return
    rule_versions = db.scalars(
        select(RuleVersion).where(RuleVersion.service_id == service.id)
    ).all()
    for rv in rule_versions:
        requirements = db.scalars(
            select(Requirement).where(Requirement.rule_version_id == rv.id)
        ).all()
        for req in requirements:
            db.query(RequirementCondition).filter(
                RequirementCondition.requirement_id == req.id
            ).delete()
            db.delete(req)
        db.query(FeeRule).filter(FeeRule.rule_version_id == rv.id).delete()
        db.delete(rv)
    questions = db.scalars(select(Question).where(Question.service_id == service.id)).all()
    for q in questions:
        db.query(QuestionCondition).filter(QuestionCondition.question_id == q.id).delete()
        conditions = db.scalars(select(Condition).where(Condition.question_id == q.id)).all()
        for c in conditions:
            db.query(RequirementCondition).filter(RequirementCondition.condition_id == c.id).delete()
            db.query(QuestionCondition).filter(QuestionCondition.condition_id == c.id).delete()
            db.delete(c)
        db.delete(q)
    db.delete(service)
    db.flush()


def _link(db: Session, requirement: Requirement, condition: Condition, negated: bool = False) -> None:
    db.add(
        RequirementCondition(requirement_id=requirement.id, condition_id=condition.id, negated=negated)
    )


def seed(db: Session) -> None:
    _wipe_existing(db)

    doc_id10 = _source_document(db, "pages_e.php?id=10")
    doc_id24 = _source_document(db, "pages_e.php?id=24")
    doc_form_pdf = _source_document(db, "applications/amendment.pdf")

    service = Service(
        code=AMENDMENT_CODE,
        name="Amend Passport Details",
        category="passports",
    )
    db.add(service)
    db.flush()

    now = datetime.now(timezone.utc)
    rv = RuleVersion(
        service_id=service.id,
        source_document_id=doc_id10.id,
        approved_by=None,
        version_number=1,
        status="draft",
        verified_at=now,
    )
    db.add(rv)
    db.flush()

    questions = {}
    for attribute, prompt, answer_type, sequence, hint in AMENDMENT_QUESTIONS:
        q = Question(
            service_id=service.id, prompt=prompt, answer_type=answer_type,
            sequence=sequence, hint=hint,
        )
        db.add(q)
        db.flush()
        questions[attribute] = q

    def make_condition(attribute: str, operator: str, value: str) -> Condition:
        c = Condition(
            question_id=questions[attribute].id, attribute=attribute, operator=operator, value=value,
        )
        db.add(c)
        db.flush()
        return c

    cond_applying_from_sri_lanka = make_condition("applying_from", "equals", "sri_lanka")
    alteration_conditions = {
        alteration: make_condition("alteration_type", "equals", alteration)
        for alteration in ALTERATION_TYPES
    }

    # district relevant only once applying_from == "sri_lanka" — same
    # mechanism every other service uses.
    db.add(
        QuestionCondition(
            question_id=questions["district"].id,
            condition_id=cond_applying_from_sri_lanka.id,
            negated=False,
        )
    )

    assert EXPECTED_ATTRIBUTES.issubset(
        {c.attribute for c in [cond_applying_from_sri_lanka, *alteration_conditions.values()]}
    ), "Seed script is missing a Condition for an expected attribute."

    # -- Application form — unconditional across every alteration type
    # and every applying_from value (no domestic/overseas form split for
    # amendment — see module docstring). Offices themselves DO differ by
    # applying_from, via the standard resolve_offices mechanism, once
    # this service resolves through the normal resolve_case path.
    application_form = Requirement(
        rule_version_id=rv.id,
        source_document_id=doc_id10.id,
        label="Completed Alteration Application Form",
        kind="prerequisite",
        freshness_rule=(
            "A hard copy can be obtained from: the Head Office, "
            "Battaramulla; the Regional Offices at Kandy, Matara, "
            "Vavuniya, Kurunegala, or Jaffna; or an Overseas Sri Lankan "
            "Mission. Delivery time for an alteration is 1 hour 30 "
            "minutes once submitted with the correct supporting "
            "documents. If printing a downloaded copy yourself, it must "
            "be laser-printed on A4 paper (pages_e.php?id=24)."
        ),
        sequence=1,
        resources=[
            {
                "label": "Alteration Application Form (Form O)",
                "url": doc_form_pdf.source_url,
                "type": "pdf",
            },
        ],
    )
    db.add(application_form)
    db.flush()

    # -- Per-alteration-type documents (source: pages_e.php?id=10's own
    # table, seq 6) — each gated on its own alteration_type value, so
    # only the documents for the alteration the citizen actually picked
    # are shown.
    alteration_docs: list[tuple[str, str, str]] = [
        ("change_of_name", "Passport", "document"),
        (
            "change_of_name",
            "Marriage certificate (to confirm name change)",
            "document",
        ),
        (
            "profession_inclusion",
            "Documents and qualification to prove profession, with photocopies",
            "document",
        ),
        (
            "nic_inclusion",
            "National Identity Card, with a photocopy",
            "document",
        ),
        (
            "cancel_single_journey",
            "National Identity Card and Birth Certificate, with photocopies",
            "document",
        ),
        (
            "cancel_india_nepal",
            "National Identity Card and Birth Certificate, with photocopies",
            "document",
        ),
        (
            "other",
            # id=10's own table leaves this cell blank — a genuine gap,
            # not filled in. Modeled as a prerequisite naming the gap
            # (not a document to bring) so a citizen picking "other"
            # isn't shown an empty checklist and left assuming nothing
            # is required.
            "Documents required for 'Other Amendments' are not "
            "specified in the Department's published fee table — "
            "confirm directly with the accepting office before "
            "applying",
            "prerequisite",
        ),
    ]
    for sequence, (alteration, label, kind) in enumerate(alteration_docs, start=2):
        req = Requirement(
            rule_version_id=rv.id, source_document_id=doc_id10.id, label=label,
            kind=kind, sequence=sequence,
        )
        db.add(req)
        db.flush()
        _link(db, req, alteration_conditions[alteration], negated=False)

    # -- Fee (source: pages_e.php?id=10 seq 6) — flat LKR 1,200 for
    # every alteration type. CHECK constraint requires normal|urgent;
    # id=10 states a single flat fee with no urgent tier, so "normal" is
    # a fixed choice to satisfy the column, not a real distinction (same
    # precedent the old phase4_renewal.py stub already established).
    db.add(
        FeeRule(
            rule_version_id=rv.id,
            source_document_id=doc_id10.id,
            base_amount=1200.00,
            basis="normal",
        )
    )

    db.flush()
    rv.status = "approved"
    rv.approved_by = "phase9-seed-script"
    db.commit()


def main() -> None:
    db = SessionLocal()
    try:
        seed(db)
        print("Phase 9 amendment rule data seeded and approved.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
