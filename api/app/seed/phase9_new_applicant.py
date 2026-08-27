"""Phase 9 seed data: New Passport (first-time applicant) service —
design.md's service #2.

"Same documents/fee/form as renewal, different citizen framing" — this
mirrors `app.seed.phase4_renewal`'s renewal-service structure closely
(same sources, same fee table, same applying_from-conditional domestic/
overseas form split built for renewal's own re-verification), with two
differences design.md is explicit about:

1. No `holds_passport` question and no CURRENT_PASSPORT-equivalent
   document Requirement — a first-time applicant has no prior passport
   to hold or submit by definition (id=8's own asterisk note: "*If you
   already have a valid passport it should be submitted along with the
   application" implies its absence is expected, not a blocker, for
   this case).
2. The standard-set NIC document is gated on age >= 16
   (`instructions_english_td.pdf` (5): "All applicants above the age of
   16 years should produce their National Identity Card") — design.md
   flags this distinction explicitly ("a first-time applicant under 16
   without an NIC yet is not the same document gap as an adult who
   simply doesn't have one... worth carrying into whichever service
   actually implements it"). Renewal's own NIC item is intentionally
   left unconditional/unchanged — this is a service-#2-specific nuance,
   not a renewal bug fix.

No amendment-alternative surfacing here (a first-time applicant has
nothing existing to amend) — `app.engine.resolver.resolve_case` already
scopes that to `passport-renewal` only via its `service_code` check.

Idempotent: re-running wipes and rebuilds `passport-new` from scratch,
same convention as `phase4_renewal.py`.

Run with:  python -m app.seed.phase9_new_applicant
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.engine.renewal_intake import NEW_APPLICANT_QUESTIONS
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

NEW_APPLICANT_CODE = "passport-new"

# Same attribute set renewal's own EXPECTED_ATTRIBUTES asserts against,
# minus holds_passport (no such question here) — see
# app.seed.phase4_renewal for why service_basis/district/applying_from
# aren't in this set.
EXPECTED_ATTRIBUTES = {
    "age",
    "name_changed",
    "dual_citizen",
    "section_19_2",
    "profession",
    "buddhist_priest",
    "applying_from",
}


def _source_document(db: Session, url_substring: str) -> SourceDocument:
    """Same resolution rule as `app.seed.phase4_renewal._source_document`
    — earliest fetch by URL, for citation stability."""
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
    service = db.scalars(select(Service).where(Service.code == NEW_APPLICANT_CODE)).first()
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
    doc_id8 = _source_document(db, "pages_e.php?id=8")
    doc_id24 = _source_document(db, "pages_e.php?id=24")
    doc_form_pdf = _source_document(db, "applications/passport_application.pdf")
    doc_form_pdf_handfill = _source_document(db, "applications/application.pdf")
    doc_instructions_pdf = _source_document(db, "applications/instructions_english_td.pdf")
    doc_om_form_pdf = _source_document(db, "applications/new_om_application_form.pdf")

    service = Service(
        code=NEW_APPLICANT_CODE,
        name="Apply for a New Passport (First-Time)",
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

    # -- Intake questions — reuses RENEWAL_QUESTIONS' own attribute/
    # prompt vocabulary via NEW_APPLICANT_QUESTIONS (see
    # app.engine.renewal_intake) — no separate wording to maintain.
    questions = {}
    for attribute, prompt, answer_type, sequence, hint in NEW_APPLICANT_QUESTIONS:
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
    cond_name_changed = make_condition("name_changed", "equals", "true")
    cond_dual_citizen = make_condition("dual_citizen", "equals", "true")
    cond_section_19_2 = make_condition("section_19_2", "equals", "true")
    cond_profession_empty = make_condition("profession", "equals", "")
    cond_buddhist_priest = make_condition("buddhist_priest", "equals", "true")
    cond_applying_from_sri_lanka = make_condition("applying_from", "equals", "sri_lanka")
    cond_applying_from_abroad = make_condition("applying_from", "equals", "abroad")

    # district relevant only once applying_from == "sri_lanka" — same
    # mechanism renewal's own re-verification built.
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
    # profession relevant only once age >= 16 — same as renewal.
    db.add(
        QuestionCondition(
            question_id=questions["profession"].id,
            condition_id=cond_age_lt_16.id,
            negated=True,
        )
    )

    assert EXPECTED_ATTRIBUTES.issubset(
        {c.attribute for c in [
            cond_age_lt_16, cond_age_lt_61, cond_name_changed, cond_dual_citizen,
            cond_section_19_2, cond_profession_empty, cond_buddhist_priest,
            cond_applying_from_sri_lanka,
        ]}
    ), "Seed script is missing a Condition for an expected attribute."

    # -- Standard document set (source: pages_e.php?id=8) — same as
    # renewal's, minus the current-passport item.
    studio_ack = Requirement(
        rule_version_id=rv.id,
        source_document_id=doc_id8.id,
        label="Photo studio acknowledgement",
        kind="prerequisite",
        freshness_rule="Photo must have been taken within the last 6 months",
        sequence=1,
    )
    db.add(studio_ack)
    db.flush()

    # Domestic and overseas application-form Requirements — identical
    # pattern to renewal's own two-Requirement split (see
    # app.seed.phase4_renewal), gated on this service's own
    # applying_from Condition rows (Condition/QuestionCondition/
    # RequirementCondition rows are per-Question, so passport-new needs
    # its own even though the underlying facts and PDFs are the same).
    domestic_application_form = Requirement(
        rule_version_id=rv.id,
        source_document_id=doc_id8.id,
        label="Completed application form K-35A",
        kind="prerequisite",
        freshness_rule=(
            "A hard copy can be obtained from: the Head Office, "
            "Battaramulla; the Regional Offices at Kandy, Matara, "
            "Vavuniya, Kurunegala, or Jaffna; or your area's Divisional "
            "Secretariat (pickup only — applications are not accepted "
            "for submission at a Divisional Secretariat). The Client "
            "Undertaking Section must be signed — no application is "
            "accepted without it. If printing a downloaded copy "
            "yourself, it must be laser-printed on A4 paper "
            "(pages_e.php?id=24)."
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
            "Submit the completed form, with supporting documents, to "
            "the Sri Lanka Embassy or Consulate in your country (or the "
            "nearest one, if none is available in your country of "
            "residence). The Client Undertaking Section must be signed "
            "and handed to the consular officer — no application is "
            "accepted without it (pages_e.php?id=9). If printing a "
            "downloaded copy yourself, it must be laser-printed on A4 "
            "paper (pages_e.php?id=24)."
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

    fingerprints = Requirement(
        rule_version_id=rv.id,
        source_document_id=doc_id7.id,
        label=(
            "Provide fingerprints in person at the Head Office or a "
            "Regional Office (required for applicants aged 16 to 60)"
        ),
        kind="prerequisite",
        sequence=3,
    )
    db.add(fingerprints)
    db.flush()
    _link(db, fingerprints, cond_age_lt_61, negated=False)
    _link(db, fingerprints, cond_age_lt_16, negated=True)

    new_nic = Requirement(
        rule_version_id=rv.id,
        source_document_id=doc_id8.id,
        label=(
            "Obtain a new National Identity Card before applying "
            "(required for dual citizenship obtained under section "
            "19(2) of the amended Citizenship Act 18 of 1948)"
        ),
        kind="prerequisite",
        sequence=19,
    )
    db.add(new_nic)
    db.flush()
    _link(db, new_nic, cond_dual_citizen, negated=False)
    _link(db, new_nic, cond_section_19_2, negated=False)

    # standard_docs — same as renewal's, minus the current-passport
    # item. The NIC item is additionally gated on age >= 16 (negated
    # cond_age_lt_16) — the one content difference from renewal's own
    # NIC item, per design.md's explicit flag (see module docstring).
    standard_docs = [
        ("Original Birth Certificate of the applicant with a photocopy.", None, 10),
        (
            "Original National Identity Card of the applicant with a photocopy",
            None,  # gated below via cond_age_lt_16 (negated) — special-cased,
            # not the generic `extra_condition` path (see the loop below)
            11,
        ),
        (
            "Marriage certificate with a photocopy where it is necessary "
            "(to confirm the name after marriage)",
            cond_name_changed,
            13,
        ),
        (
            "Educational Certificate related to the profession and an "
            "acceptable document to confirm your service, with photocopies",
            None,  # gated below via cond_profession_empty (negated)
            14,
        ),
        (
            "Samanera certificate or Higher Ordination certificate, "
            "with photocopies (mandatory for Buddhist priests)",
            cond_buddhist_priest,
            15,
        ),
    ]
    for label, extra_condition, sequence in standard_docs:
        req = Requirement(
            rule_version_id=rv.id, source_document_id=doc_id8.id, label=label,
            kind="document", sequence=sequence,
        )
        db.add(req)
        db.flush()
        _link(db, req, cond_dual_citizen, negated=True)  # apply only when NOT dual citizen
        if label.startswith("Original National Identity Card"):
            _link(db, req, cond_age_lt_16, negated=True)  # NOT age < 16 => age >= 16
        elif extra_condition is not None:
            _link(db, req, extra_condition, negated=False)
        if label.startswith("Educational Certificate"):
            _link(db, req, cond_profession_empty, negated=True)  # profession stated

    # -- Dual-citizen document set (replaces the standard set) — same as
    # renewal's. Not age-gated: this project doesn't assert a minimum
    # age for dual citizenship anywhere in the sources read, so no
    # unsourced restriction is added here either.
    dual_docs = [
        ("Dual Citizenship Certificate with a photocopy.", 21),
        (
            "Foreign passport with any Sri Lankan passport if there is "
            "(with photocopy of Bio data pages)",
            22,
        ),
        ("National Identity Card with a photocopy.", 23),
        ("Birth Certificate with a photocopy.", 24),
    ]
    for label, sequence in dual_docs:
        req = Requirement(
            rule_version_id=rv.id, source_document_id=doc_id8.id, label=label,
            kind="document", sequence=sequence,
        )
        db.add(req)
        db.flush()
        _link(db, req, cond_dual_citizen, negated=False)

    # -- Fees (source: pages_e.php?id=8) — identical table to renewal's;
    # id=8's fee/timeline/office table doesn't distinguish first-time
    # from renewal at all (design.md).
    db.add_all(
        [
            FeeRule(rule_version_id=rv.id, source_document_id=doc_id8.id, base_amount=10000.00, basis="normal"),
            FeeRule(rule_version_id=rv.id, source_document_id=doc_id8.id, base_amount=20000.00, basis="urgent"),
            FeeRule(
                rule_version_id=rv.id, source_document_id=doc_id8.id,
                condition_id=cond_age_lt_16.id, base_amount=3000.00, basis="normal",
            ),
            FeeRule(
                rule_version_id=rv.id, source_document_id=doc_id8.id,
                condition_id=cond_age_lt_16.id, base_amount=9000.00, basis="urgent",
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
        print("Phase 9 new-applicant (first-time) rule data seeded and approved.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
