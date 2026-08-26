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
    QuestionCondition,
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
    # Added with the Downloads-page re-verification: applying_from now
    # gates a Requirement too (which application form applies), not just
    # the district QUESTION — see below.
    "applying_from",
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
            db.query(QuestionCondition).filter(
                QuestionCondition.question_id == q.id
            ).delete()
            conditions = db.scalars(
                select(Condition).where(Condition.question_id == q.id)
            ).all()
            for c in conditions:
                db.query(RequirementCondition).filter(
                    RequirementCondition.condition_id == c.id
                ).delete()
                db.query(QuestionCondition).filter(
                    QuestionCondition.condition_id == c.id
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
    doc_id24 = _source_document(db, "pages_e.php?id=24")
    doc_form_pdf = _source_document(db, "applications/passport_application.pdf")
    doc_form_pdf_handfill = _source_document(db, "applications/application.pdf")
    doc_instructions_pdf = _source_document(db, "applications/instructions_english_td.pdf")
    doc_om_form_pdf = _source_document(db, "applications/new_om_application_form.pdf")

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
    for attribute, prompt, answer_type, sequence, hint in RENEWAL_QUESTIONS:
        q = Question(
            service_id=renewal_service.id,
            prompt=prompt,
            answer_type=answer_type,
            sequence=sequence,
            hint=hint,
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
    # Gates the district question (below) AND, as of the Downloads-page
    # re-verification (pages_e.php?id=24), which application-form
    # Requirement applies — the domestic K-35A vs. the Overseas Missions
    # Passport Application. Two separate Condition rows (not one
    # in/negated pair) so each reads as its own positive fact, matching
    # this file's existing style for other two-valued attributes.
    cond_applying_from_sri_lanka = make_condition("applying_from", "equals", "sri_lanka")
    cond_applying_from_abroad = make_condition("applying_from", "equals", "abroad")

    # -- Question relevance (data-driven, not a code special-case) --------
    # buddhist_priest carries NO suppressing condition — it is asked of
    # every applicant unconditionally, regardless of profession (bug fix
    # — manual QA bug #6). It previously used to be skipped once
    # profession named a secular occupation, but monks in Sri Lanka
    # commonly also hold one (teacher, scholar, lecturer); suppressing
    # the question on that basis silently excluded a monk who answered
    # e.g. "teacher" from the Samanera/Higher Ordination certificate
    # requirement, which is mandatory for priests regardless of any other
    # occupation. Question ORDER also changed to ask buddhist_priest
    # before profession (see RENEWAL_QUESTIONS) so this can never again
    # be implemented as "skip based on the profession just given."
    #
    # profession itself IS gated — on age, not on any other answer (bug
    # fix — manual QA bug #5): reuses cond_age_lt_16 negated, so it's
    # relevant only once the applicant is known to be 16 or older
    # (mirrors the fingerprint requirement's own use of this same
    # condition). This is close to redundant with the scope gate (bug
    # fix #2) — a true under-16 case is refused immediately after age is
    # recorded and never reaches this question via the normal chat flow
    # — but is kept as an explicit, defense-in-depth gate on the
    # question's own relevance data, not solely on that separate
    # code-level short-circuit (e.g. GET /case/{id}/next-question calls
    # `next_question` directly and has no scope-gate check of its own).
    db.add(
        QuestionCondition(
            question_id=questions["profession"].id,
            condition_id=cond_age_lt_16.id,
            negated=True,  # relevant unless age < 16
        )
    )

    # district is gated on applying_from == "sri_lanka" (Phase 9's
    # renewal re-verification, replacing an earlier fragile fix that
    # tried to recognize "abroad"/"overseas" phrases directly against
    # the district question itself). A citizen answering "abroad" to
    # applying_from is never asked which Sri Lankan district they're
    # in — id=9's Mission path has no district concept at all. Every
    # other renewal question (age, holds_passport, name_changed,
    # dual_citizen, section_19_2, buddhist_priest, profession) still
    # applies to an overseas applicant per the sources read for this
    # phase — none of id=7/id=8/id=9 states otherwise for those facts.
    # service_basis (normal/urgent) was considered and deliberately left
    # ungated too: id=9 is silent on whether one-day service exists for
    # Mission submissions — asserting it doesn't would be inventing a
    # fact no source states (this project's own "conflicts kept
    # surfaced, not resolved" convention — see design.md).
    db.add(
        QuestionCondition(
            question_id=questions["district"].id,
            condition_id=cond_applying_from_sri_lanka.id,
            negated=False,  # relevant only once applying_from == "sri_lanka"
        )
    )

    assert EXPECTED_ATTRIBUTES.issubset(
        {c.attribute for c in [
            cond_age_lt_16, cond_age_lt_61, cond_name_changed, cond_holds_passport,
            cond_dual_citizen, cond_section_19_2, cond_profession_empty, cond_buddhist_priest,
            cond_applying_from_sri_lanka,
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

    # Application form K-35A — DOMESTIC variant only as of the
    # Downloads-page re-verification (pages_e.php?id=24): gated on
    # applying_from == "sri_lanka" (below). An overseas applicant gets a
    # different Requirement entirely — the Overseas Missions Passport
    # Application, right after this one — id=24's own "Overseas
    # Missions" section labels it "Only for overseas applicants", and
    # id=9 describes a materially different submission channel (through
    # a Mission, never a domestic office). Sequenced before the document
    # items (10+): the form must be obtained and filled before the
    # supporting documents are assembled around it. Source: pages_e.php
    # ?id=8, "Where can I obtain an Application Form?" for the pickup
    # locations; the PDF URLs are the exact ones the scraper fetched
    # (SOURCE_DOCUMENT.source_url), not hand-typed, so they're already
    # verified as live. Divisional Secretariats are named here only as a
    # form-pickup location — never as a submission location;
    # `app.engine.offices.resolve_offices` never selects a `type=ds`
    # office, so the plan's offices list can't imply otherwise either.
    # "Overseas Sri Lankan Mission" dropped from this pickup list (it
    # used to be listed here) — this Requirement is domestic-only now,
    # and a Mission wouldn't hand out the domestic form variant anyway.
    #
    # Two downloadable variants, both Form K-35A, both offered (id=24's
    # own "Downloadable Format" column distinguishes them): "Online Fill
    # and Printable" (fill on-screen, then print) and "Downloadable"
    # (print blank, then fill by hand) — a citizen without a computer to
    # fill the first one still has a usable path. Neither label is this
    # project's own wording; id=24's own column headers are quoted
    # directly rather than asserting which one is "for" handwriting
    # (not stated in so many words on either PDF read for this).
    #
    # phase-9-service-expansion re-verification: this used to also
    # assert "the application must be filled in English" — traced back
    # during Phase 9's full re-read of id=7/id=8/id=9/id=10 and found
    # unsourced; no fetched page or PDF states an English-only
    # requirement (see design.md's "Forms" general-info entry, which
    # flags this specifically as a gap). Removed rather than left in on
    # the strength of an untraceable claim. The Client Undertaking
    # Section signature requirement IS sourced — from id=9 ("This
    # section has to be signed by the applicant... No application will
    # be accepted without applicant's signature in CUS"), not id=8 (this
    # Requirement's own source_document_id) — a minor citation mismatch
    # kept as a single Requirement rather than split, since K-35A is the
    # same form regardless of which channel a citizen reads about it on.
    #
    # Printing note added per id=24's own instruction, applies to every
    # downloadable form offered anywhere in this seed (both variants
    # here, and the Overseas Missions form below).
    application_form = Requirement(
        rule_version_id=renewal_rv.id,
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
    db.add(application_form)
    db.flush()
    _link(db, application_form, cond_applying_from_sri_lanka, negated=False)

    # Overseas Missions Passport Application — the overseas counterpart
    # to the domestic K-35A above, gated on applying_from == "abroad".
    # id=24's "Overseas Missions" section: "Overseas Missions Passport
    # Application (Only for overseas applicants)", still labeled
    # "Form K - 35 A" but a DIFFERENT PDF (new_om_application_form.pdf,
    # not passport_application.pdf/application.pdf) — its own extracted
    # text confirms it also covers a child under 16 and an Emergency/
    # Identity Certificate application on the same form (fields for a
    # parent/guardian's details "If this application is for a child
    # below the age of 16 years", and the form's own header:
    # "APPLICATION FOR A SRI LANKAN PASSPORT, EMERGENCY/IDENTITY
    # CERTIFICATE") — relevant to `passport-under-16`/`emergency-
    # certificate` once those services are built, not encoded here since
    # this Requirement lives on `passport-renewal` only. Submission
    # channel and the CUS signature requirement are id=9's (seq 3): the
    # form is submitted to the Sri Lanka Embassy/Consulate, with the
    # Client Undertaking Section signed and handed to the consular
    # officer — cited here from id=9 despite this Requirement's own
    # source_document_id being id=24 (where the specific PDF/label
    # facts are confirmed), same minor-citation-mismatch precedent the
    # domestic Requirement above already carries.
    #
    # The five OM annexes (i-v) are deliberately NOT added as
    # Requirements here — see design.md's "Overseas Missions form set"
    # note: annex iii (parent's consent) and iv (lost/stolen complaint)
    # don't apply to an adult renewal at all (they belong to the
    # not-yet-built under-16 and lost-stolen services respectively), and
    # annexes i/ii/v's real trigger conditions (a citizenship-proof
    # certificate type, PR/settlement status abroad, and section 5(2)
    # registration specifically) aren't facts this intake collects for
    # any service yet — adding them unconditionally would show a
    # renewing overseas citizen with an ordinary passport three
    # affidavits that don't apply to them, which is exactly the
    # "wrong checklist is worse than no checklist" failure mode
    # CLAUDE.md warns against. Left as a documented gap, not guessed.
    overseas_application_form = Requirement(
        rule_version_id=renewal_rv.id,
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
        rule_version_id=renewal_rv.id,
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
    # "Completed application form" (previously its own dual-citizen-only
    # document item here, sequence 20) is now the same K-35A form the
    # new unconditional `application_form` prerequisite above already
    # covers for every renewal case, dual citizen or not — removed here
    # to avoid showing a citizen the same form as two separate checklist
    # items.
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
    # The below-16 tier reuses `cond_age_lt_16` (already created above
    # for the fingerprints requirement) via FeeRule.condition_id — the
    # Phase 2 schema already supports a conditional fee rule, this is
    # its first use. Added for langgraph-orchestration-branch's
    # tool-selection-instability fix: a golden-set scenario surfaced
    # that `get_fee` had no way to return this tier at all, since it was
    # never seeded as structured data, only present in the source page's
    # text — see design.md.
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
            FeeRule(
                rule_version_id=renewal_rv.id,
                source_document_id=doc_id8.id,
                condition_id=cond_age_lt_16.id,
                base_amount=3000.00,
                basis="normal",
            ),
            FeeRule(
                rule_version_id=renewal_rv.id,
                source_document_id=doc_id8.id,
                condition_id=cond_age_lt_16.id,
                base_amount=9000.00,
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
