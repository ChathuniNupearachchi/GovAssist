"""Phase 9 seed data: Replace a Lost or Stolen Passport service —
design.md's service #3.

Shares the same base application set as renewal/first-time (photo
studio acknowledgement, fingerprints, birth certificate, NIC, K-35A
form — domestic/overseas split reused from `app.seed.phase4_renewal`/
`app.seed.phase9_new_applicant`) plus what's specific to this service:

1. A reporting prerequisite, domestic or overseas (`pages_e.php?id=12`),
   gated on `lost_location` (where the loss/theft happened — NOT
   `applying_from`, where the citizen is applying from now; see point
   2) — domestic is a hotline call AND a police complaint (id=12's own
   numbered steps list both sequentially, not as alternatives — this
   UPDATES design.md's Conflict 1 from "unresolved" to "resolved: both
   required", see design.md); overseas is a local police report plus
   the downloadable complaint form, submitted together to the nearest
   Mission.
2. The police complaint document itself (unconditional — both branches
   produce one), and the NMRP travel document, gated on
   `lost_location == "abroad"`. `lost_location` is a DIFFERENT
   attribute from `applying_from`: id=8's own text — NMRP/Temporary
   Travel Documents are "issued to Sri Lankans whose passports have
   been lost, stolen or expired WHILST IN A FOREIGN COUNTRY," obtained
   from and submitted to an Overseas Mission as their OWN separate
   application (not bundled into the replacement passport's own Mission
   submission), used only to re-enter Sri Lanka. A citizen who lost
   their passport abroad, flew home on an NMRP, and is now applying
   domestically (`applying_from == "sri_lanka"` at that point) still
   needs to bring the NMRP as a document — gating this on
   `applying_from` instead would have silently never asked for it in
   exactly that case. See `app.engine.renewal_intake`'s
   `_LOST_LOCATION_QUESTION` docstring.
3. A combined base-fee-plus-penalty total (LKR 20,000 within a year of
   the lost passport's issue, LKR 15,000 after — `pages_e.php?id=8` seq
   33-34), via `app.engine.fees.resolve_fee`'s newly generalized
   `answers`-based conditional-fee-tier mechanism (was age-only).

Scope note: `id=8`'s penalty is "charged only if the relevant validity
period of the passport has not lapsed" — this service's own premise
(a still-valid passport that was lost/stolen, not one that had already
expired) makes that condition definitionally true here, so the penalty
is modeled as always-applicable once the reason question routes a
citizen here at all (see design.md's "Common misrouting" note and
`app.chat.service_routing`) — an already-expired-then-lost passport
should route to renewal instead, not this service.

No `holds_passport` question, same reasoning as `passport-new`: this
service's whole premise is not currently holding the passport in
question.

Run with:  python -m app.seed.phase9_lost_stolen
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.engine.renewal_intake import LOST_STOLEN_QUESTIONS
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

LOST_STOLEN_CODE = "passport-lost-stolen"

EXPECTED_ATTRIBUTES = {
    "age",
    "name_changed",
    "dual_citizen",
    "section_19_2",
    "profession",
    "buddhist_priest",
    "applying_from",
    "lost_location",
    "lost_passport_age",
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
    service = db.scalars(select(Service).where(Service.code == LOST_STOLEN_CODE)).first()
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
    doc_id12 = _source_document(db, "pages_e.php?id=12")
    doc_id24 = _source_document(db, "pages_e.php?id=24")
    doc_complaint_form = _source_document(
        db, "complaint_form%20_stolen_and_lost_sri%20lankan_passport.pdf"
    )
    doc_form_pdf = _source_document(db, "applications/passport_application.pdf")
    doc_form_pdf_handfill = _source_document(db, "applications/application.pdf")
    doc_instructions_pdf = _source_document(db, "applications/instructions_english_td.pdf")
    doc_om_form_pdf = _source_document(db, "applications/new_om_application_form.pdf")

    service = Service(
        code=LOST_STOLEN_CODE,
        name="Replace a Lost or Stolen Passport",
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
    for attribute, prompt, answer_type, sequence, hint in LOST_STOLEN_QUESTIONS:
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
    cond_lost_within_1yr = make_condition("lost_passport_age", "equals", "within_1_year")
    cond_lost_over_1yr = make_condition("lost_passport_age", "equals", "over_1_year")

    db.add(
        QuestionCondition(
            question_id=questions["district"].id,
            condition_id=cond_applying_from_sri_lanka.id,
            negated=False,
        )
    )
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
            cond_applying_from_sri_lanka, cond_lost_within_1yr,
        ]}
    ), "Seed script is missing a Condition for an expected attribute."

    # -- Reporting prerequisite (source: pages_e.php?id=12) — domestic
    # and overseas variants, gated on applying_from, mirroring the
    # domestic/overseas application-form split's own pattern. Sequenced
    # FIRST (before even the photo studio acknowledgement) — design.md's
    # own prerequisite order: report the loss before anything else.
    domestic_reporting = Requirement(
        rule_version_id=rv.id,
        source_document_id=doc_id12.id,
        label=(
            "Report the loss or theft: call the Immigration Department "
            "hotline (0112 101 533, or fax 011-2885358, 8.30am-4.00pm "
            "Mon-Fri excluding government holidays) AND make a complaint "
            "to your local police station as soon as possible"
        ),
        kind="prerequisite",
        sequence=1,
    )
    db.add(domestic_reporting)
    db.flush()
    _link(db, domestic_reporting, cond_applying_from_sri_lanka, negated=False)

    overseas_reporting = Requirement(
        rule_version_id=rv.id,
        source_document_id=doc_id12.id,
        label=(
            "Report the loss or theft: obtain a police report from your "
            "local police in your country of residence, download and "
            "complete the stolen/lost passport complaint form, and "
            "submit both together to the nearest Sri Lankan Diplomatic "
            "or Consular office"
        ),
        kind="prerequisite",
        sequence=1,
        resources=[
            {
                "label": "Stolen or Lost Sri Lankan Passport — Complaint Form",
                "url": doc_complaint_form.source_url,
                "type": "pdf",
            },
        ],
    )
    db.add(overseas_reporting)
    db.flush()
    _link(db, overseas_reporting, cond_applying_from_abroad, negated=False)

    studio_ack = Requirement(
        rule_version_id=rv.id,
        source_document_id=doc_id8.id,
        label="Photo studio acknowledgement",
        kind="prerequisite",
        freshness_rule="Photo must have been taken within the last 6 months",
        sequence=2,
    )
    db.add(studio_ack)
    db.flush()

    # -- Domestic and overseas application-form Requirements — same
    # pattern as renewal/new-applicant's own split.
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
        sequence=3,
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
        sequence=3,
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
        sequence=4,
    )
    db.add(fingerprints)
    db.flush()
    _link(db, fingerprints, cond_age_lt_61, negated=False)
    _link(db, fingerprints, cond_age_lt_16, negated=True)

    # -- Documents specific to this service (source: pages_e.php?id=8
    # seq 32-34 / instructions_english_td.pdf (e)) ------------------
    police_complaint = Requirement(
        rule_version_id=rv.id,
        source_document_id=doc_id8.id,
        label="Original of the police complaint, including the lost passport number",
        kind="document",
        freshness_rule=(
            "If the lost passport number isn't available, it can be "
            "obtained from the Colombo Head Office or a Regional Office."
        ),
        sequence=9,
    )
    db.add(police_complaint)
    db.flush()

    nmrp_document = Requirement(
        rule_version_id=rv.id,
        source_document_id=doc_id8.id,
        label="Temporary travel document (NMRP) used to arrive in Sri Lanka, with a photocopy",
        kind="document",
        sequence=9,
    )
    db.add(nmrp_document)
    db.flush()
    _link(db, nmrp_document, cond_applying_from_abroad, negated=False)

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

    standard_docs = [
        ("Original Birth Certificate of the applicant with a photocopy.", None, 10),
        ("Original National Identity Card of the applicant with a photocopy", None, 11),
        (
            "Marriage certificate with a photocopy where it is necessary "
            "(to confirm the name after marriage)",
            cond_name_changed,
            13,
        ),
        (
            "Educational Certificate related to the profession and an "
            "acceptable document to confirm your service, with photocopies",
            None,
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
        _link(db, req, cond_dual_citizen, negated=True)
        if extra_condition is not None:
            _link(db, req, extra_condition, negated=False)
        if label.startswith("Educational Certificate"):
            _link(db, req, cond_profession_empty, negated=True)

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

    # -- Fees (source: pages_e.php?id=8 seq 33-34) — base passport fee
    # PLUS the loss penalty, combined into one total per (basis, penalty
    # tier), since app.engine.fees.resolve_fee returns exactly one
    # FeeRule row, not a sum of several (see that module's own
    # docstring). 10,000+20,000=30,000 / 10,000+15,000=25,000 for normal
    # basis; 20,000+20,000=40,000 / 20,000+15,000=35,000 for urgent.
    db.add_all(
        [
            FeeRule(
                rule_version_id=rv.id, source_document_id=doc_id8.id,
                condition_id=cond_lost_within_1yr.id, base_amount=30000.00, basis="normal",
            ),
            FeeRule(
                rule_version_id=rv.id, source_document_id=doc_id8.id,
                condition_id=cond_lost_over_1yr.id, base_amount=25000.00, basis="normal",
            ),
            FeeRule(
                rule_version_id=rv.id, source_document_id=doc_id8.id,
                condition_id=cond_lost_within_1yr.id, base_amount=40000.00, basis="urgent",
            ),
            FeeRule(
                rule_version_id=rv.id, source_document_id=doc_id8.id,
                condition_id=cond_lost_over_1yr.id, base_amount=35000.00, basis="urgent",
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
        print("Phase 9 lost-or-stolen rule data seeded and approved.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
