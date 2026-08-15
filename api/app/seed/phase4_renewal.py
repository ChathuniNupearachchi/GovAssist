"""Phase 4 seed data: adult passport renewal and passport amendment.

Hand-enters the rule content described in the phase-4-rules-engine
change's proposal.md/design.md into the schema built in Phase 2 (and
extended in this phase with per-fact source citations and
RESOLUTION_NOTE). Every fact below was verified directly against the
extracted text of pages_e.php?id=7, id=8, and id=10 (see design.md's
Context) before being hand-entered here.

Idempotent: re-running this script wipes and rebuilds the
`passport-renewal` and `passport-amendment` services (and the
`urgent_office_conflict` resolution note) from scratch, so it is safe to
run repeatedly against a dev database without accumulating duplicates.

Run with:  python -m app.seed.phase4_renewal
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.engine.renewal_intake import RENEWAL_QUESTIONS
from app.models import (
    Condition,
    FeeRule,
    Office,
    Question,
    Requirement,
    RequirementCondition,
    ResolutionNote,
    RuleVersion,
    Service,
    SourceDocument,
)

RENEWAL_CODE = "passport-renewal"
AMENDMENT_CODE = "passport-amendment"
CONFLICT_NOTE_CODE = "urgent_office_conflict"

# Every semantic fact this seed asserts a Condition.attribute for. The
# seed's own assert step (design.md's typo-mitigation) checks all of
# these exist before either rule version is marked approved.
EXPECTED_ATTRIBUTES = {
    "age",
    "name_changed",
    "holds_passport",
    "dual_citizen",
    "section_19_2",
    "profession",
    "buddhist_priest",
}
# "service_basis" and "district" intentionally have no Condition row:
# the fee calculator compares the case's basis answer directly against
# FeeRule.basis, and the office resolver reads OFFICE.district directly
# — neither needs a REQUIREMENT_CONDITION-linked Condition (design.md's
# office resolver precedence).


def _source_document(db: Session, url_substring: str) -> SourceDocument:
    """Resolve a SourceDocument by URL, taking the earliest fetch.

    Two SourceDocument rows exist per ingested URL from Phase 3's
    re-scrape (content differs only by a live visitor counter — see that
    change's design.md). Citations must be stable, so this always
    resolves to the first/original fetch (design.md's Risk mitigation).
    """
    doc = db.scalars(
        select(SourceDocument)
        .where(SourceDocument.source_url.like(f"%{url_substring}"))
        .order_by(SourceDocument.fetched_at.asc())
    ).first()
    if doc is None:
        raise RuntimeError(
            f"No ingested SourceDocument found for '{url_substring}' — "
            "run Phase 3's scraper before seeding Phase 4 rule data."
        )
    return doc


def _wipe_existing(db: Session) -> None:
    """Delete any prior Phase 4 seed output so this script is re-runnable."""
    for code in (RENEWAL_CODE, AMENDMENT_CODE):
        service = db.scalars(select(Service).where(Service.code == code)).first()
        if service is None:
            continue
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
        questions = db.scalars(
            select(Question).where(Question.service_id == service.id)
        ).all()
        for q in questions:
            conditions = db.scalars(
                select(Condition).where(Condition.question_id == q.id)
            ).all()
            for c in conditions:
                db.query(RequirementCondition).filter(
                    RequirementCondition.condition_id == c.id
                ).delete()
                db.delete(c)
            db.delete(q)
        db.delete(service)
    existing_note = db.scalars(
        select(ResolutionNote).where(ResolutionNote.code == CONFLICT_NOTE_CODE)
    ).first()
    if existing_note is not None:
        db.delete(existing_note)
    db.flush()


def _link(db: Session, requirement: Requirement, condition: Condition, negated: bool = False) -> None:
    db.add(
        RequirementCondition(
            requirement_id=requirement.id, condition_id=condition.id, negated=negated
        )
    )


def seed(db: Session) -> None:
    _wipe_existing(db)

    doc_id8 = _source_document(db, "pages_e.php?id=8")
    doc_id7 = _source_document(db, "pages_e.php?id=7")
    doc_id10 = _source_document(db, "pages_e.php?id=10")

    # -- Offices -----------------------------------------------------
    # Head Office + 5 Regional Offices already exist from Phase 2's seed.
    # Add a mission-type office if one doesn't exist yet (id=8's
    # submission list includes Overseas Sri Lankan Missions, and no
    # Divisional Secretariat is ever an accepting office for renewal —
    # DS offices distribute forms only, per id=8's two different lists).
    mission = db.scalars(select(Office).where(Office.type == "mission")).first()
    if mission is None:
        mission = Office(
            name="Overseas Sri Lankan Missions",
            type="mission",
            district=None,
            opening_hours="Varies by mission — contact the relevant Sri Lankan mission",
        )
        db.add(mission)
        db.flush()

    # -- Services ------------------------------------------------------
    renewal_service = Service(
        code=RENEWAL_CODE, name="Renew an Ordinary Passport", category="passports"
    )
    amendment_service = Service(
        code=AMENDMENT_CODE, name="Amend Passport Details", category="passports"
    )
    db.add_all([renewal_service, amendment_service])
    db.flush()

    # -- Rule versions ---------------------------------------------------
    now = datetime.now(timezone.utc)
    renewal_rv = RuleVersion(
        service_id=renewal_service.id,
        source_document_id=doc_id8.id,
        approved_by=None,
        version_number=1,
        status="draft",
        verified_at=now,
    )
    amendment_rv = RuleVersion(
        service_id=amendment_service.id,
        source_document_id=doc_id10.id,
        approved_by=None,
        version_number=1,
        status="draft",
        verified_at=now,
    )
    db.add_all([renewal_rv, amendment_rv])
    db.flush()

    # -- Renewal intake questions ---------------------------------------
    # RENEWAL_QUESTIONS is shared with app.engine.next_question so seeding
    # and next-question logic can't drift apart on the question<->attribute
    # mapping (Question itself carries no attribute column).
    questions = {}
    for attribute, prompt, answer_type, sequence in RENEWAL_QUESTIONS:
        q = Question(
            service_id=renewal_service.id,
            prompt=prompt,
            answer_type=answer_type,
            sequence=sequence,
        )
        db.add(q)
        db.flush()
        questions[attribute] = q

    # -- Conditions --------------------------------------------------
    # Operators restricted to equals/lessThan/in (Phase 2 schema); ages
    # 16-60 is expressed as two lessThan conditions combined via two
    # REQUIREMENT_CONDITION links (one negated) rather than a single
    # "between" operator that doesn't exist — see design.md.
    def make_condition(attribute: str, operator: str, value: str) -> Condition:
        c = Condition(
            question_id=questions[attribute].id,
            attribute=attribute,
            operator=operator,
            value=value,
        )
        db.add(c)
        db.flush()
        return c

    cond_age_lt_16 = make_condition("age", "lessThan", "16")
    cond_age_lt_61 = make_condition("age", "lessThan", "61")
    cond_name_changed = make_condition("name_changed", "equals", "true")
    cond_holds_passport = make_condition("holds_passport", "equals", "true")
    cond_dual_citizen = make_condition("dual_citizen", "equals", "true")
    cond_section_19_2 = make_condition("section_19_2", "equals", "true")
    # "profession stated" = profession answer is not empty. Expressed as
    # equals("") negated on the requirement link, rather than a fourth
    # operator — see design.md's Condition.attribute decision.
    cond_profession_empty = make_condition("profession", "equals", "")
    cond_buddhist_priest = make_condition("buddhist_priest", "equals", "true")

    assert EXPECTED_ATTRIBUTES.issubset(
        {c.attribute for c in [
            cond_age_lt_16, cond_age_lt_61, cond_name_changed, cond_holds_passport,
            cond_dual_citizen, cond_section_19_2, cond_profession_empty, cond_buddhist_priest,
        ]}
    ), "Seed script is missing a Condition for an expected attribute — see design.md's Risk mitigation."

    # -- Standard document set (source: pages_e.php?id=8, "Ordinary Passports") --
    studio_ack = Requirement(
        rule_version_id=renewal_rv.id,
        source_document_id=doc_id8.id,
        label="Photo studio acknowledgement",
        kind="prerequisite",
        freshness_rule="Photo must have been taken within the last 6 months",
        sequence=1,
    )
    db.add(studio_ack)
    db.flush()

    fingerprints = Requirement(
        rule_version_id=renewal_rv.id,
        source_document_id=doc_id7.id,
        label=(
            "Provide fingerprints in person at the Head Office or a "
            "Regional Office (required for applicants aged 16 to 60)"
        ),
        kind="prerequisite",
        sequence=2,
    )
    db.add(fingerprints)
    db.flush()
    _link(db, fingerprints, cond_age_lt_61, negated=False)  # age < 61
    _link(db, fingerprints, cond_age_lt_16, negated=True)  # NOT age < 16  => age >= 16

    new_nic = Requirement(
        rule_version_id=renewal_rv.id,
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
            "Current passport with a photocopy of the Bio data page.",
            cond_holds_passport,
            12,
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
            rule_version_id=renewal_rv.id,
            source_document_id=doc_id8.id,
            label=label,
            kind="document",
            sequence=sequence,
        )
        db.add(req)
        db.flush()
        _link(db, req, cond_dual_citizen, negated=True)  # apply only when NOT dual citizen
        if extra_condition is not None:
            _link(db, req, extra_condition, negated=False)
        if label.startswith("Educational Certificate"):
            _link(db, req, cond_profession_empty, negated=True)  # profession stated

    # -- Dual-citizen document set (replaces the standard set) -----------
    dual_docs = [
        ("Completed application form", 20),
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
            rule_version_id=renewal_rv.id,
            source_document_id=doc_id8.id,
            label=label,
            kind="document",
            sequence=sequence,
        )
        db.add(req)
        db.flush()
        _link(db, req, cond_dual_citizen, negated=False)

    # -- Fees (source: pages_e.php?id=8) ---------------------------------
    db.add_all(
        [
            FeeRule(
                rule_version_id=renewal_rv.id,
                source_document_id=doc_id8.id,
                base_amount=10000.00,
                basis="normal",
            ),
            FeeRule(
                rule_version_id=renewal_rv.id,
                source_document_id=doc_id8.id,
                base_amount=20000.00,
                basis="urgent",
            ),
        ]
    )

    # -- Resolution note: the urgent-service office conflict --------------
    db.add(
        ResolutionNote(
            code=CONFLICT_NOTE_CODE,
            note_text=(
                "pages_e.php?id=7 states in one section that one-day "
                "(urgent) service is \"only available at\" the Head "
                "Office, but the same page's working-hours section lists "
                "\"Application for One day Service – 7.30am onwards on "
                "weekdays\" for the Regional Offices at Kandy, Matara, "
                "Vavuniya, Kurunegala and Jaffna too. pages_e.php?id=8 "
                "draws no location distinction for urgent service at "
                "all. Confirm with the office directly before traveling "
                "for urgent service at a Regional Office."
            ),
            primary_source_document_id=doc_id7.id,
            secondary_source_document_id=doc_id7.id,
        )
    )

    # -- Amendment service (source: pages_e.php?id=10) ---------------------
    db.add(
        FeeRule(
            rule_version_id=amendment_rv.id,
            source_document_id=doc_id10.id,
            base_amount=1200.00,
            # CHECK constraint requires normal|urgent; amendment has no
            # urgent/normal split in the source (a single flat fee), so
            # this is a fixed choice to satisfy the column, not a real
            # distinction — see design.md.
            basis="normal",
        )
    )
    db.add_all(
        [
            Requirement(
                rule_version_id=amendment_rv.id,
                source_document_id=doc_id10.id,
                label="Passport",
                kind="document",
                sequence=1,
            ),
            Requirement(
                rule_version_id=amendment_rv.id,
                source_document_id=doc_id10.id,
                label="Marriage certificate (to confirm name change)",
                kind="document",
                sequence=2,
            ),
        ]
    )

    db.flush()

    # -- Approve both rule versions ---------------------------------------
    renewal_rv.status = "approved"
    renewal_rv.approved_by = "phase4-seed-script"
    amendment_rv.status = "approved"
    amendment_rv.approved_by = "phase4-seed-script"

    db.commit()


def main() -> None:
    db = SessionLocal()
    try:
        seed(db)
        print("Phase 4 renewal + amendment rule data seeded and approved.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
