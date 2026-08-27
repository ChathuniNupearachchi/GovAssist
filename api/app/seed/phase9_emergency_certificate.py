"""Phase 9 seed data: Emergency Certificate (India and Nepal) —
design.md's service #7, the last of the seven.

The most gap-limited service built: `id=7` seq 9 confirms eligibility
("Emergency Certificates for Buddhist Pilgrims travel India and
Nepal"); `instructions_english_td.pdf` (f)(ii) confirms the fee (LKR
500, no urgent tier — shown as "–"); `instructions_english_td.pdf`
(a)(2)(ii) confirms it's a K-35A tick-box option, same form as every
other service. NO source states a document list specific to this
certificate (design.md, checked directly again this session — id=8 has
zero mentions of "emergency", id=24 has zero mentions of "emergency").

Requirements here are therefore limited to what's independently,
generally sourced — not a copied-over adult document list:
- The K-35A form itself (domestic/overseas split, reused).
- Photo studio acknowledgement (id=7 seq 12: "All applicants should
  obtain their photographs only from studios authorized by the
  Department" — unscoped, not an Ordinary-Passport-specific fact).
- Fingerprints, age 16-60 (id=7 seq 13: "every applicant above 16... and
  below 60... must provide his or her fingerprints" — same unscoped
  framing, same condition mechanism renewal/new/lost-stolen/under-16
  already use).
- An explicit note on what this document is (and isn't) for — id=7's
  own eligibility statement, surfaced directly per design.md's "Common
  misrouting": a citizen might not realize this narrower, cheaper
  document exists, or might mistakenly think it works for travel
  beyond India/Nepal, which it explicitly does not.

No `service_basis` question (no urgent tier exists for this fee).
Timeline/offices: not independently confirmed for this narrower
document either (design.md flags this too) — offices still resolve via
the standard applying_from-aware mechanism (a structural fact about
which office accepts an application, not a citizen-specific
requirement), noted as unconfirmed in the form Requirement's own text,
same treatment `app.seed.phase9_under_16` gave its own unconfirmed
timeline/offices.

Run with:  python -m app.seed.phase9_emergency_certificate
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.engine.renewal_intake import EMERGENCY_CERTIFICATE_QUESTIONS
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

EMERGENCY_CERTIFICATE_CODE = "emergency-certificate"

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
    service = db.scalars(select(Service).where(Service.code == EMERGENCY_CERTIFICATE_CODE)).first()
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

    doc_id7 = _source_document(db, "pages_e.php?id=7")
    doc_id24 = _source_document(db, "pages_e.php?id=24")
    doc_instructions_pdf = _source_document(db, "applications/instructions_english_td.pdf")
    doc_form_pdf = _source_document(db, "applications/passport_application.pdf")
    doc_form_pdf_handfill = _source_document(db, "applications/application.pdf")
    doc_om_form_pdf = _source_document(db, "applications/new_om_application_form.pdf")

    service = Service(
        code=EMERGENCY_CERTIFICATE_CODE,
        name="Emergency Certificate (India and Nepal)",
        category="passports",
    )
    db.add(service)
    db.flush()

    now = datetime.now(timezone.utc)
    rv = RuleVersion(
        service_id=service.id,
        source_document_id=doc_id7.id,
        approved_by=None,
        version_number=1,
        status="draft",
        verified_at=now,
    )
    db.add(rv)
    db.flush()

    questions = {}
    for attribute, prompt, answer_type, sequence, hint in EMERGENCY_CERTIFICATE_QUESTIONS:
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

    cond_age_lt_16 = make_condition("age", "lessThan", "16")
    cond_age_lt_61 = make_condition("age", "lessThan", "61")
    cond_applying_from_sri_lanka = make_condition("applying_from", "equals", "sri_lanka")
    cond_applying_from_abroad = make_condition("applying_from", "equals", "abroad")

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

    assert EXPECTED_ATTRIBUTES.issubset({cond_applying_from_sri_lanka.attribute}), (
        "Seed script is missing a Condition for an expected attribute."
    )

    # -- Eligibility/scope note — surfaced first, per design.md's
    # "Common misrouting": stated plainly so a citizen doesn't mistake
    # this for a general travel document, or fail to realize this
    # narrower/cheaper option exists for pilgrimage specifically.
    eligibility_note = Requirement(
        rule_version_id=rv.id,
        source_document_id=doc_id7.id,
        label=(
            "This Emergency Certificate is valid ONLY for travel to "
            "India or Nepal (Buddhist pilgrimage) — it is not a "
            "general travel document and cannot be used for travel to "
            "any other country"
        ),
        kind="prerequisite",
        sequence=1,
    )
    db.add(eligibility_note)
    db.flush()

    # -- Application form — same K-35A/OM form split as every other
    # service; the OM form's own header explicitly names "EMERGENCY/
    # IDENTITY CERTIFICATE" alongside "PASSPORT".
    domestic_application_form = Requirement(
        rule_version_id=rv.id,
        source_document_id=doc_id7.id,
        label="Completed application form K-35A (tick 'Emergency Certificates (India and Nepal)')",
        kind="prerequisite",
        freshness_rule=(
            "A hard copy can be obtained from: the Head Office, "
            "Battaramulla; the Regional Offices at Kandy, Matara, "
            "Vavuniya, Kurunegala, or Jaffna; or your area's Divisional "
            "Secretariat (pickup only — applications are not accepted "
            "for submission at a Divisional Secretariat). Timeline and "
            "office details specific to this certificate are not "
            "independently confirmed in any source read — the office "
            "list above is the general one every K-35A application "
            "uses. If printing a downloaded copy yourself, it must be "
            "laser-printed on A4 paper (pages_e.php?id=24)."
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
        label="Completed Overseas Missions Passport Application form (tick 'Emergency/Identity Certificate')",
        kind="prerequisite",
        freshness_rule=(
            "Submit the completed form, with supporting documents, to "
            "the Sri Lanka Embassy or Consulate in your country (or the "
            "nearest one, if none is available in your country of "
            "residence). If printing a downloaded copy yourself, it "
            "must be laser-printed on A4 paper (pages_e.php?id=24)."
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
        source_document_id=doc_id7.id,
        label="Photo studio acknowledgement",
        kind="prerequisite",
        freshness_rule="Photo must have been taken within the last 6 months",
        sequence=3,
    )
    db.add(studio_ack)
    db.flush()

    fingerprints = Requirement(
        rule_version_id=rv.id,
        source_document_id=doc_id7.id,
        label=(
            "Provide fingerprints in person at the Head Office or a "
            "Regional Office (required for applicants aged 16 to 60)"
        ),
        kind="prerequisite",
        sequence=4,
    )
    db.add(fingerprints)
    db.flush()
    _link(db, fingerprints, cond_age_lt_61, negated=False)
    _link(db, fingerprints, cond_age_lt_16, negated=True)

    # -- Fee (source: instructions_english_td.pdf (f)(ii)) — flat
    # LKR 500, no urgent tier (shown as "–" in the fee table) and no
    # separate child tier stated for this document.
    db.add(
        FeeRule(
            rule_version_id=rv.id,
            source_document_id=doc_instructions_pdf.id,
            base_amount=500.00,
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
        print("Phase 9 Emergency Certificate rule data seeded and approved.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
