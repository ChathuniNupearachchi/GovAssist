"""Phase 9 seed data: Passport for a Child Under 16 — design.md's
service #5.

Longest conditional document list of any service built so far — id=8
seq 23-27 / `instructions_english_td.pdf` (c)(i)-(x) document real,
sourced branching on facts no other service asks about: whether the
parents hold valid passports, whether the child was ever included in a
parent's passport before (must be removed first — Form I.E. 35C, a
prerequisite for service #6 once built), a deceased/divorced/abandoned
family circumstance, adoption, and overseas birth. Every one of these
gates an actual Requirement below — none guessed, none flattened into
an unconditional list a family whose situation is simpler would be
shown irrelevant documents for.

Reuses the SAME domestic/overseas application-form split every other
service already has — `instructions_english_td.pdf` section (a)'s own
heading confirms "Form K - I.E. 35 A" is the SAME form number as the
adult K-35A application (point (19) specifically addresses "the father
or guardian... if the application is of a child less than 16 years of
age"), and the Overseas Missions form's own extracted text already
covers a child under 16 on the same form (fields 18+) — see
`app.ingestion.sources.py`'s `new_om_application_form.pdf` entry. No
new form to ingest for this service.

Scope gate: `app.engine.resolver.resolve_case`'s under-16 scope gate is
now conditional on `service_code != "passport-under-16"` — this is the
one service that specifically needs to accept an under-16 `age` answer
rather than refuse it.

Run with:  python -m app.seed.phase9_under_16
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.engine.renewal_intake import UNDER_16_QUESTIONS
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

UNDER_16_CODE = "passport-under-16"

EXPECTED_ATTRIBUTES = {
    "applying_from",
    "parents_hold_passport",
    "child_previously_in_parent_passport",
    "parent_circumstance",
    "child_adopted",
    "child_born_overseas",
    "validity_period",
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
    service = db.scalars(select(Service).where(Service.code == UNDER_16_CODE)).first()
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

    doc_id8 = _source_document(db, "pages_e.php?id=8")
    doc_id24 = _source_document(db, "pages_e.php?id=24")
    doc_instructions_pdf = _source_document(db, "applications/instructions_english_td.pdf")
    doc_form_pdf = _source_document(db, "applications/passport_application.pdf")
    doc_form_pdf_handfill = _source_document(db, "applications/application.pdf")
    doc_om_form_pdf = _source_document(db, "applications/new_om_application_form.pdf")
    doc_request_letter = _source_document(db, "applications/request_letter.pdf")

    service = Service(
        code=UNDER_16_CODE,
        name="Apply for a Child's Passport (Under 16)",
        category="passports",
    )
    db.add(service)
    db.flush()

    now = datetime.now(timezone.utc)
    rv = RuleVersion(
        service_id=service.id,
        source_document_id=doc_id8.id,
        approved_by=None,
        version_number=1,
        status="draft",
        verified_at=now,
    )
    db.add(rv)
    db.flush()

    questions = {}
    for attribute, prompt, answer_type, sequence, hint in UNDER_16_QUESTIONS:
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
    cond_applying_from_abroad = make_condition("applying_from", "equals", "abroad")
    cond_parents_hold_passport = make_condition("parents_hold_passport", "equals", "true")
    cond_child_previously_in_parent_passport = make_condition(
        "child_previously_in_parent_passport", "equals", "true"
    )
    cond_parent_deceased = make_condition("parent_circumstance", "equals", "deceased")
    cond_parent_divorced = make_condition("parent_circumstance", "equals", "divorced")
    cond_child_abandoned = make_condition("parent_circumstance", "equals", "abandoned")
    cond_child_adopted = make_condition("child_adopted", "equals", "true")
    cond_child_born_overseas = make_condition("child_born_overseas", "equals", "true")
    cond_validity_3yr = make_condition("validity_period", "equals", "3_year")
    cond_validity_10yr = make_condition("validity_period", "equals", "10_year")

    db.add(
        QuestionCondition(
            question_id=questions["district"].id,
            condition_id=cond_applying_from_sri_lanka.id,
            negated=False,
        )
    )
    # photo_district — same gate (item 5 of the intake-parsing fix).
    db.add(
        QuestionCondition(
            question_id=questions["photo_district"].id,
            condition_id=cond_applying_from_sri_lanka.id,
            negated=False,
        )
    )

    assert EXPECTED_ATTRIBUTES.issubset(
        {c.attribute for c in [
            cond_applying_from_sri_lanka, cond_parents_hold_passport,
            cond_child_previously_in_parent_passport, cond_parent_deceased,
            cond_child_adopted, cond_child_born_overseas, cond_validity_3yr,
        ]}
    ), "Seed script is missing a Condition for an expected attribute."

    # -- Prerequisites -------------------------------------------------
    both_parents_attend = Requirement(
        rule_version_id=rv.id,
        source_document_id=doc_instructions_pdf.id,
        label=(
            "Both parents, or the legal guardian, must be present to "
            "hand over the application in person"
        ),
        kind="prerequisite",
        sequence=1,
    )
    db.add(both_parents_attend)
    db.flush()

    domestic_application_form = Requirement(
        rule_version_id=rv.id,
        source_document_id=doc_id8.id,
        label="Completed application form K-35A",
        kind="prerequisite",
        freshness_rule=(
            "Same form as the adult application (also referred to as "
            "Form K-I.E. 35(A) in the Department's own instructions), "
            "with additional fields for a parent or guardian's details. "
            "A hard copy can be obtained from: the Head Office, "
            "Battaramulla; the Regional Offices at Kandy, Matara, "
            "Vavuniya, Kurunegala, or Jaffna; or your area's Divisional "
            "Secretariat (pickup only — applications are not accepted "
            "for submission at a Divisional Secretariat). If printing a "
            "downloaded copy yourself, it must be laser-printed on A4 "
            "paper (pages_e.php?id=24)."
        ),
        sequence=2,
        resources=[
            {
                "label": "Application form K-35A (Online Fill and Printable)",
                "url": doc_form_pdf.source_url,
                "type": "pdf",
            },
            {
                "label": "Application form K-35A (Downloadable — fill by hand)",
                "url": doc_form_pdf_handfill.source_url,
                "type": "pdf",
            },
            {
                "label": "Filling instructions",
                "url": doc_instructions_pdf.source_url,
                "type": "pdf",
            },
        ],
    )
    db.add(domestic_application_form)
    db.flush()
    _link(db, domestic_application_form, cond_applying_from_sri_lanka, negated=False)

    overseas_application_form = Requirement(
        rule_version_id=rv.id,
        source_document_id=doc_id24.id,
        label="Completed Overseas Missions Passport Application form",
        kind="prerequisite",
        freshness_rule=(
            "The same Overseas Missions form used for adult applications "
            "covers a child's application too — it has its own fields "
            "for a parent or guardian's details when the applicant is "
            "under 16. Submit the completed form, with supporting "
            "documents, to the Sri Lanka Embassy or Consulate in your "
            "country (or the nearest one, if none is available in your "
            "country of residence). If printing a downloaded copy "
            "yourself, it must be laser-printed on A4 paper "
            "(pages_e.php?id=24)."
        ),
        sequence=2,
        resources=[
            {
                "label": "Overseas Missions Passport Application (Form K-35A, overseas applicants only)",
                "url": doc_om_form_pdf.source_url,
                "type": "pdf",
            },
        ],
    )
    db.add(overseas_application_form)
    db.flush()
    _link(db, overseas_application_form, cond_applying_from_abroad, negated=False)

    studio_ack = Requirement(
        rule_version_id=rv.id,
        source_document_id=doc_id8.id,
        label="Photo studio acknowledgement",
        kind="prerequisite",
        freshness_rule="Photo must have been taken within the last 6 months",
        sequence=3,
    )
    db.add(studio_ack)
    db.flush()

    # Child-name-deletion first, if applicable — a prerequisite ACTION,
    # not a document to bring. instructions_english_td.pdf (c)(viii):
    # "If the child's name was ever included in either of parent's
    # passport, it should be cancelled first before obtaining a
    # separate passport for the child. The form I.E. 35C should be
    # filled and a fee of Rs.1,200 will be charged." Cites the fact
    # directly rather than a specific service #6 Requirement — that
    # service isn't built yet (see design.md's implementation order).
    deletion_first = Requirement(
        rule_version_id=rv.id,
        source_document_id=doc_instructions_pdf.id,
        label=(
            "The child's name must first be removed from the parent's "
            "passport before a separate passport can be issued (Form "
            "I.E. 35C, LKR 1,200) — complete this before applying here"
        ),
        kind="prerequisite",
        sequence=4,
    )
    db.add(deletion_first)
    db.flush()
    _link(db, deletion_first, cond_child_previously_in_parent_passport, negated=False)

    # -- Documents -------------------------------------------------------
    birth_cert = Requirement(
        rule_version_id=rv.id,
        source_document_id=doc_instructions_pdf.id,
        label="Original birth certificate of the child, with a photocopy",
        kind="document",
        freshness_rule=(
            "An English translation of the birth certificate is NOT "
            "accepted as the original."
        ),
        sequence=10,
    )
    db.add(birth_cert)
    db.flush()

    parents_passport_doc = Requirement(
        rule_version_id=rv.id,
        source_document_id=doc_id8.id,
        label=(
            "Parents' passports, with photocopies of the data page and "
            "the page showing the child's particulars"
        ),
        kind="document",
        sequence=11,
    )
    db.add(parents_passport_doc)
    db.flush()
    _link(db, parents_passport_doc, cond_parents_hold_passport, negated=False)

    parents_no_passport_doc = Requirement(
        rule_version_id=rv.id,
        source_document_id=doc_id8.id,
        label=(
            "National Identity Cards of both parents, with photocopies, "
            "and an affidavit confirming the parents do not hold a "
            "valid Sri Lankan passport"
        ),
        kind="document",
        sequence=11,
    )
    db.add(parents_no_passport_doc)
    db.flush()
    _link(db, parents_no_passport_doc, cond_parents_hold_passport, negated=True)

    consent_letter = Requirement(
        rule_version_id=rv.id,
        source_document_id=doc_instructions_pdf.id,
        label="Consent letter of the parents (or legal guardian)",
        kind="document",
        freshness_rule=(
            "If either or both parents are abroad, their letter of "
            "consent must be endorsed by the Sri Lankan Embassy or High "
            "Commission in the relevant country."
        ),
        sequence=12,
        resources=[
            {
                "label": "Request to issue a separate passport to child",
                "url": doc_request_letter.source_url,
                "type": "pdf",
            },
        ],
    )
    db.add(consent_letter)
    db.flush()

    current_passport = Requirement(
        rule_version_id=rv.id,
        source_document_id=doc_id8.id,
        label=(
            "Current passport with a photocopy of the Bio data page, "
            "if the child already has one"
        ),
        kind="document",
        sequence=13,
    )
    db.add(current_passport)
    db.flush()

    # -- Family-circumstance documents — mutually exclusive branches of
    # parent_circumstance (see app.engine.renewal_intake's
    # _PARENT_CIRCUMSTANCE_QUESTION docstring).
    deceased_docs = Requirement(
        rule_version_id=rv.id,
        source_document_id=doc_id8.id,
        label=(
            "Original death certificate(s), the surviving parent's or "
            "legal guardian's identification document, the guardian's "
            "consent letter, and a report from the Grama Niladhari "
            "attested by the Divisional Secretary"
        ),
        kind="document",
        sequence=20,
    )
    db.add(deceased_docs)
    db.flush()
    _link(db, deceased_docs, cond_parent_deceased, negated=False)

    divorced_docs = Requirement(
        rule_version_id=rv.id,
        source_document_id=doc_id8.id,
        label="Original divorce certificate and the court order stating custody of the child",
        kind="document",
        sequence=20,
    )
    db.add(divorced_docs)
    db.flush()
    _link(db, divorced_docs, cond_parent_divorced, negated=False)

    abandoned_docs = Requirement(
        rule_version_id=rv.id,
        source_document_id=doc_id8.id,
        label=(
            "Certified copy of the police report and a confirmation "
            "letter from the Grama Niladhari, countersigned by the "
            "Divisional Secretary"
        ),
        kind="document",
        sequence=20,
    )
    db.add(abandoned_docs)
    db.flush()
    _link(db, abandoned_docs, cond_child_abandoned, negated=False)

    adoption_docs = Requirement(
        rule_version_id=rv.id,
        source_document_id=doc_id8.id,
        label=(
            "Certificate of Adoption, the court order, and a letter "
            "from the Commissioner of Probation and Child Care"
        ),
        kind="document",
        sequence=21,
    )
    db.add(adoption_docs)
    db.flush()
    _link(db, adoption_docs, cond_child_adopted, negated=False)

    citizenship_cert = Requirement(
        rule_version_id=rv.id,
        source_document_id=doc_instructions_pdf.id,
        label=(
            "Sri Lankan Citizenship certificate issued by the "
            "Department of Immigration and Emigration, with a photocopy"
        ),
        kind="document",
        sequence=22,
    )
    db.add(citizenship_cert)
    db.flush()
    _link(db, citizenship_cert, cond_child_born_overseas, negated=False)

    # -- Fees (source: pages_e.php?id=8 seq 28-29) — validity-tier
    # dependent, no unconditional fallback (validity_period is always
    # answered before resolving, same pattern as lost-stolen's penalty
    # tiers — see app.engine.fees's own generalized `answers` mechanism).
    db.add_all(
        [
            FeeRule(
                rule_version_id=rv.id, source_document_id=doc_id8.id,
                condition_id=cond_validity_3yr.id, base_amount=3000.00, basis="normal",
            ),
            FeeRule(
                rule_version_id=rv.id, source_document_id=doc_id8.id,
                condition_id=cond_validity_3yr.id, base_amount=9000.00, basis="urgent",
            ),
            FeeRule(
                rule_version_id=rv.id, source_document_id=doc_id8.id,
                condition_id=cond_validity_10yr.id, base_amount=10000.00, basis="normal",
            ),
            FeeRule(
                rule_version_id=rv.id, source_document_id=doc_id8.id,
                condition_id=cond_validity_10yr.id, base_amount=20000.00, basis="urgent",
            ),
        ]
    )

    db.flush()
    rv.status = "approved"
    rv.approved_by = "phase9-seed-script"
    db.commit()


def main() -> None:
    db = SessionLocal()
    try:
        seed(db)
        print("Phase 9 under-16 rule data seeded and approved.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
