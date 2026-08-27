"""Phase 9 seed data: Delete a Child's Name from a Parent's Passport —
design.md's service #6.

The shortest service built so far: one document, one form, one flat
fee, no alteration-type branching (unlike amendment) and no domestic/
overseas FORM split (unlike renewal/new/lost-stolen/under-16) — id=24
lists only one "Children Deletion"/"Form C" download, so
`applying_from` here only changes which OFFICE accepts the application
(same mechanism amendment uses), not which form is required.

**Form — Conflict 3's resolution, applied**: cites `child_deletion_
application.pdf` ("Form C" per id=24) directly, NOT `amendment.pdf`
("Form O") — design.md's "Revised recommendation" once this service
was actually built. "Form I.E. 35C" (`instructions_english_td.pdf`'s
own label for what is very likely the same document) is disclosed in
the Requirement's own detail text as a related, unconfirmed-identical
label — per explicit instruction, because filing the wrong form risks
outright rejection, this reasoning belongs in the citizen-facing detail
text, not only a citation.

**Fee**: LKR 1,200, confirmed by two independent clean sources (id=10's
alteration table; instructions_english_td.pdf (c)(viii)) — no
dependency on `child_deletion_application.pdf`'s own (still garbled)
extracted text for this figure.

Run with:  python -m app.seed.phase9_child_deletion
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.engine.renewal_intake import CHILD_DELETION_QUESTIONS
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

CHILD_DELETION_CODE = "passport-child-deletion"

EXPECTED_ATTRIBUTES = {
    "applying_from",
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
    service = db.scalars(select(Service).where(Service.code == CHILD_DELETION_CODE)).first()
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
    doc_instructions_pdf = _source_document(db, "applications/instructions_english_td.pdf")
    doc_child_deletion_form = _source_document(db, "applications/child_deletion_application.pdf")

    service = Service(
        code=CHILD_DELETION_CODE,
        name="Delete a Child's Name from a Passport",
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
    for attribute, prompt, answer_type, sequence, hint in CHILD_DELETION_QUESTIONS:
        q = Question(
            service_id=service.id, prompt=prompt, answer_type=answer_type,
            sequence=sequence, hint=hint,
        )
        db.add(q)
        db.flush()
        questions[attribute] = q

    cond_applying_from_sri_lanka = Condition(
        question_id=questions["applying_from"].id,
        attribute="applying_from", operator="equals", value="sri_lanka",
    )
    db.add(cond_applying_from_sri_lanka)
    db.flush()

    db.add(
        QuestionCondition(
            question_id=questions["district"].id,
            condition_id=cond_applying_from_sri_lanka.id,
            negated=False,
        )
    )

    assert EXPECTED_ATTRIBUTES.issubset({cond_applying_from_sri_lanka.attribute}), (
        "Seed script is missing a Condition for an expected attribute."
    )

    # -- Application form — Form C, NOT Form O (Conflict 3's resolution
    # — see module docstring). Unconditional: only one form regardless
    # of applying_from (no domestic/overseas split for this service).
    application_form = Requirement(
        rule_version_id=rv.id,
        source_document_id=doc_id24.id,
        label="Completed Children Deletion Application Form (Form C)",
        kind="prerequisite",
        freshness_rule=(
            "This is a DIFFERENT form from the general Alteration "
            "Application Form ('Form O') used for every other "
            "amendment — filing the wrong one risks the application "
            "being rejected. The Department's own instructions "
            "(instructions_english_td.pdf) separately refer to this "
            "requirement as \"Form I.E. 35C\" — very likely the same "
            "document as Form C, but this has not been independently "
            "confirmed; if in doubt, confirm with the office directly "
            "before relying on either label alone. Delivery time is "
            "reasonably the same 1 hour 30 minutes as other "
            "alterations, though not separately confirmed for this "
            "one. If printing a downloaded copy yourself, it must be "
            "laser-printed on A4 paper (pages_e.php?id=24)."
        ),
        sequence=1,
        resources=[
            {
                "label": "Children Deletion Application Form (Form C)",
                "url": doc_child_deletion_form.source_url,
                "type": "pdf",
            },
        ],
    )
    db.add(application_form)
    db.flush()

    # -- Document (source: pages_e.php?id=10 seq 6, "Deletion of a
    # child's name | Passport | LKR 1,200.00") -----------------------
    passport_doc = Requirement(
        rule_version_id=rv.id,
        source_document_id=doc_id10.id,
        label="Passport (the one listing the child to be removed)",
        kind="document",
        sequence=10,
    )
    db.add(passport_doc)
    db.flush()

    # -- Fee (source: pages_e.php?id=10 seq 6; independently confirmed
    # by instructions_english_td.pdf (c)(viii)) — flat LKR 1,200, no
    # urgent tier stated for this alteration type, same "normal" fixed
    # choice convention amendment already established.
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
        print("Phase 9 child-name-deletion rule data seeded and approved.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
