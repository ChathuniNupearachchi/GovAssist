"""Shared question data for the renewal service's intake.

A single source of truth for (attribute, prompt, answer_type, sequence),
imported by both `app.seed.phase4_renewal` (which persists these as
`Question` rows) and `app.engine.next_question` (which needs to map a
persisted `Question` back to the semantic attribute the condition
evaluator and the golden test fixtures key answers by). `Question` itself
carries no attribute column — see design.md's "Condition.attribute names
the semantic fact" decision — so this module is what keeps seeding and
next-question logic from drifting apart on that mapping.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.engine.conditions import condition_link_passes
from app.models import Question, QuestionCondition

# (attribute, prompt, answer_type, sequence, hint)
#
# `hint` carries a legal/technical reference for a citizen (or a
# reviewer) who already knows the terminology, shown alongside — never
# instead of — the plain-language `prompt`. Only `section_19_2` has one;
# every other question is answerable without any legislative knowledge
# to begin with, so there's nothing to hint at (`hint` is `None` for the
# rest, not an empty string — "no reference exists" is a different fact
# than "reference is blank"). See conversational-intake's plain-language
# audit: every prompt below was checked against "would answering this
# require knowing an Act, a section number, or legal terminology?" and
# rewritten where it did.
RENEWAL_QUESTIONS: list[tuple[str, str, str, int, str | None]] = [
    ("age", "How old is the applicant?", "single", 1, None),
    # applying_from moved to sequence 2, ahead of holds_passport (Phase
    # 9's Downloads-page re-verification): it closes off more branches
    # than any other question except age — it determines the form set
    # (domestic K-35A vs. the Overseas Missions application), the office
    # list, whether fingerprints happen at intake or on first return to
    # Sri Lanka, and (per the sources read for this) whether urgent
    # service is even offered at all. age stays first regardless — it
    # gates the under-16 scope check, a hard stop that must run before
    # anything else. See design.md's "Intake ordering" note.
    (
        "applying_from",
        "Are you applying from inside Sri Lanka, or from abroad?",
        "single",
        2,
        None,
    ),
    (
        "holds_passport",
        "Do you still hold your current or a previous passport?",
        "boolean",
        3,
        None,
    ),
    (
        "name_changed",
        "Has your name changed since your passport was issued?",
        "boolean",
        4,
        None,
    ),
    ("dual_citizen", "Are you a dual citizen?", "boolean", 5, None),
    (
        "section_19_2",
        "Did you apply for dual citizenship through the special "
        "provisions route, rather than the standard application?",
        "boolean",
        6,
        "Legal reference: section 19(2) of the Citizenship Act, "
        "as amended by Act No. 18 of 1948.",
    ),
    # buddhist_priest is asked BEFORE profession, and unconditionally
    # (bug fix — manual QA bug #6): monks in Sri Lanka commonly also
    # hold a secular profession (teacher, scholar, lecturer), so a
    # profession-based suppression of this question — the prior design —
    # silently excluded a monk who answered e.g. "teacher" from the
    # Samanera/Higher Ordination certificate requirement, which is
    # mandatory for priests regardless of any other occupation they also
    # hold. See app.seed.phase4_renewal: no QUESTION_CONDITION is linked
    # to this question anymore.
    ("buddhist_priest", "Are you a Buddhist priest?", "boolean", 7, None),
    (
        "profession",
        "What is your job or occupation? (leave blank if you don't have one)",
        "single",
        8,
        None,
    ),
    ("district", "Which district are you applying from?", "district", 9, None),
    # Item 5 of this change's own report: the applying district and the
    # photo district are different facts — someone applying in Colombo
    # may live and photograph in Gampaha. Domestic-only (gated on
    # applying_from == "sri_lanka" in every seed script that reuses this
    # question, same as `district` itself) — an overseas applicant's
    # photo studio is a matter for their own country, out of scope for
    # this app's Sri Lankan studio directory. `answer_type="district"`
    # reuses the same district-picker validation `district` uses.
    # `hint` (not `prompt`) is where the "default to the applying
    # district" suggestion lives — `prompt` stays the plain-language
    # question rephrase.py can present standalone; the rephrase job
    # already receives recent conversation turns (including the
    # citizen's own district answer), so it can naturally suggest that
    # district by name without a separate mechanism. The deterministic
    # pass additionally accepts a bare "same"/"yes" as literally meaning
    # the applying district (see deterministic.py's `_match_photo_
    # district` and nodes.py's classify_node) — the citizen never has to
    # retype a district they already gave.
    (
        "photo_district",
        "Which district will you take your passport photograph in?",
        "district",
        10,
        "If it's the same district you're applying from, just say \"same\".",
    ),
    (
        "service_basis",
        "Do you need normal service, or urgent (same-day) service?",
        "single",
        11,
        None,
    ),
]

# New passport (first-time applicant) — design.md service #2: "same
# documents/fee/form as renewal, different citizen framing," so this
# reuses RENEWAL_QUESTIONS' exact attribute vocabulary and prompt
# wording (kept in ATTRIBUTE_BY_PROMPT/next_question/deterministic.py
# unchanged — no new question text to maintain in three places) rather
# than a hand-duplicated list that could silently drift from renewal's.
#
# Two questions are dropped, not just `holds_passport`. BUG FIX (question
# audit, item 2 of this correction round): `name_changed`'s prompt is
# "Has your name changed since your passport was issued?" — that
# presupposes a prior passport a first-time applicant by definition
# doesn't have, exactly like `holds_passport`. Both are dropped for the
# same reason; neither is meaningful here. This also retires the
# marriage-certificate Requirement that used to be gated on
# `name_changed` for this service (see `app.seed.phase9_new_applicant`)
# — a first-time applicant whose name differs from their birth
# certificate (e.g. a married name) is a real, sourced case
# (id=8's "Marriage certificate... where necessary"), but re-asking it
# correctly for this service (without presupposing a prior passport) is
# new question text this correction doesn't introduce; recorded as a
# known scope gap here rather than silently left half-wired to a
# question that will never fire.
NEW_APPLICANT_QUESTIONS: list[tuple[str, str, str, int, str | None]] = [
    (attribute, prompt, answer_type, index, hint)
    for index, (attribute, prompt, answer_type, _sequence, hint) in enumerate(
        (q for q in RENEWAL_QUESTIONS if q[0] not in ("holds_passport", "name_changed")),
        start=1,
    )
]

# Replace a lost or stolen passport — design.md service #3. Same
# reasoning as NEW_APPLICANT_QUESTIONS (no `holds_passport` — the
# applicant doesn't currently hold the passport in question, that's the
# premise of the service), PLUS one genuinely new question this
# service needs and no other one does: how long ago the lost/stolen
# passport was issued, which selects the LKR 20,000/15,000 penalty tier
# (pages_e.php?id=8 seq 33-34) — see `app.seed.phase9_lost_stolen`.
_LOST_PASSPORT_AGE_QUESTION: tuple[str, str, str, int, str | None] = (
    "lost_passport_age",
    "Was the passport you lost or had stolen issued within the last "
    "year, or more than a year ago?",
    "single",
    0,  # placeholder — renumbered below
    None,
)
# A SECOND new question, distinct from `applying_from` — where the
# passport was lost/stolen, not where the citizen is applying from now.
# id=8's own text: NMRP/Temporary Travel Documents are "issued to Sri
# Lankans whose passports have been lost, stolen or expired WHILST IN A
# FOREIGN COUNTRY," obtained from and submitted to an Overseas Mission
# — its own separate application, not bundled into the replacement
# passport's own Mission submission. A citizen who lost their passport
# abroad, flew home on an NMRP, and is now applying domestically
# (`applying_from == "sri_lanka"` at that point) still needs to bring
# the NMRP as a document — conflating this with `applying_from` would
# have silently never asked for it in exactly that case. Reporting
# (domestic hotline+police vs. overseas police report+complaint form)
# is also gated on THIS attribute, not `applying_from` — a citizen
# reports where the loss happened, which is a fact about the past, not
# necessarily where they are now applying from. See
# `app.seed.phase9_lost_stolen`.
_LOST_LOCATION_QUESTION: tuple[str, str, str, int, str | None] = (
    "lost_location",
    "Was the passport lost or stolen inside Sri Lanka, or abroad?",
    "single",
    0,  # placeholder — renumbered below
    None,
)
_lost_stolen_shared = [q for q in RENEWAL_QUESTIONS if q[0] not in ("holds_passport", "service_basis")]
_lost_stolen_basis = next(q for q in RENEWAL_QUESTIONS if q[0] == "service_basis")
LOST_STOLEN_QUESTIONS: list[tuple[str, str, str, int, str | None]] = [
    (attribute, prompt, answer_type, index, hint)
    for index, (attribute, prompt, answer_type, _sequence, hint) in enumerate(
        (
            *_lost_stolen_shared,
            _LOST_LOCATION_QUESTION,
            _LOST_PASSPORT_AGE_QUESTION,
            _lost_stolen_basis,
        ),
        start=1,
    )
]

# Amend an existing passport — design.md service #4. Much smaller
# question set than the other three: amendment doesn't ask any of
# renewal's identity/eligibility facts (dual_citizen, buddhist_priest,
# etc.) — the citizen already holds the passport being altered, so the
# only new facts needed are WHICH alteration and (per id=10's own
# office list — Head Office/Regional Offices/Overseas Sri Lankan
# Missions, same set renewal uses) WHERE they're applying from.
# `age`/`applying_from` reused verbatim from RENEWAL_QUESTIONS (same
# attribute, same wording — no separate text to maintain); `district`
# reused too, gated the same applying_from-conditional way. No
# `service_basis` — id=10 states a single flat fee/timeline, no
# normal/urgent split (`app.seed.phase9_amendment`).
_amendment_age = next(q for q in RENEWAL_QUESTIONS if q[0] == "age")
_amendment_applying_from = next(q for q in RENEWAL_QUESTIONS if q[0] == "applying_from")
_amendment_district = next(q for q in RENEWAL_QUESTIONS if q[0] == "district")
# No `photo_district` here (unlike renewal/new-applicant/lost-stolen/
# under-16/emergency-certificate) — amendment has no "Photo studio
# acknowledgement" Requirement at all (confirmed against
# app.seed.phase9_amendment: the citizen already holds a valid photo on
# their existing passport, no new one is taken), so asking which
# district a photo will be taken in would be actively wrong here.
_ALTERATION_TYPE_QUESTION: tuple[str, str, str, int, str | None] = (
    "alteration_type",
    "What would you like to change or correct on your passport?",
    "single",
    0,  # placeholder — renumbered below
    None,
)
AMENDMENT_QUESTIONS: list[tuple[str, str, str, int, str | None]] = [
    (attribute, prompt, answer_type, index, hint)
    for index, (attribute, prompt, answer_type, _sequence, hint) in enumerate(
        (
            _amendment_age,
            _amendment_applying_from,
            _amendment_district,
            _ALTERATION_TYPE_QUESTION,
        ),
        start=1,
    )
]

# Passport for a child under 16 — design.md service #5. `age`/
# `applying_from`/`district`/`service_basis` reused verbatim (same
# attributes/wording — "the applicant" is the child throughout this
# app's existing convention, unchanged here). `holds_passport` is NOT
# reused — a child hasn't held a passport before by definition (same
# reasoning as passport-new). Everything else is new: id=8 seq 23-27 /
# `instructions_english_td.pdf` (c)(i)-(x) document a materially longer
# list of conditional documents than any other service — which parent
# facts and family circumstances apply determines a genuinely different
# checklist, not just a swapped form (see `app.seed.phase9_under_16`).
# `parent_circumstance` collapses three of id=8's special-circumstance
# facts (deceased/divorced/abandoned parent) into one single-choice
# question rather than three independent booleans — they're
# realistically mutually exclusive for one case, and a 3-boolean
# version would ask the same substance across three separate turns.
_under16_age = next(q for q in RENEWAL_QUESTIONS if q[0] == "age")
_under16_applying_from = next(q for q in RENEWAL_QUESTIONS if q[0] == "applying_from")
_under16_district = next(q for q in RENEWAL_QUESTIONS if q[0] == "district")
_under16_photo_district = next(q for q in RENEWAL_QUESTIONS if q[0] == "photo_district")
_under16_service_basis = next(q for q in RENEWAL_QUESTIONS if q[0] == "service_basis")
_VALIDITY_PERIOD_QUESTION: tuple[str, str, str, int, str | None] = (
    "validity_period",
    "Would you like a 3-year or 10-year validity passport for the child?",
    "single",
    0,
    None,
)
_PARENTS_HOLD_PASSPORT_QUESTION: tuple[str, str, str, int, str | None] = (
    "parents_hold_passport",
    "Do both parents currently hold a valid Sri Lankan passport?",
    "boolean",
    0,
    None,
)
_CHILD_PREVIOUSLY_IN_PARENT_PASSPORT_QUESTION: tuple[str, str, str, int, str | None] = (
    "child_previously_in_parent_passport",
    "Was the child ever included in a parent's passport before?",
    "boolean",
    0,
    None,
)
_PARENT_CIRCUMSTANCE_QUESTION: tuple[str, str, str, int, str | None] = (
    "parent_circumstance",
    "Is either parent deceased, are the parents divorced, or was the "
    "child abandoned by their parents? If none of these apply, just "
    "say so.",
    "single",
    0,
    None,
)
_CHILD_ADOPTED_QUESTION: tuple[str, str, str, int, str | None] = (
    "child_adopted",
    "Is the child adopted?",
    "boolean",
    0,
    None,
)
_CHILD_BORN_OVERSEAS_QUESTION: tuple[str, str, str, int, str | None] = (
    "child_born_overseas",
    "Was the child born outside Sri Lanka?",
    "boolean",
    0,
    None,
)
UNDER_16_QUESTIONS: list[tuple[str, str, str, int, str | None]] = [
    (attribute, prompt, answer_type, index, hint)
    for index, (attribute, prompt, answer_type, _sequence, hint) in enumerate(
        (
            _under16_age,
            _under16_applying_from,
            _under16_district,
            _under16_photo_district,
            _PARENTS_HOLD_PASSPORT_QUESTION,
            _CHILD_PREVIOUSLY_IN_PARENT_PASSPORT_QUESTION,
            _PARENT_CIRCUMSTANCE_QUESTION,
            _CHILD_ADOPTED_QUESTION,
            _CHILD_BORN_OVERSEAS_QUESTION,
            _VALIDITY_PERIOD_QUESTION,
            _under16_service_basis,
        ),
        start=1,
    )
]

# Delete a child's name from a parent's passport — design.md service
# #6. The shortest question set of any service: only `age`/
# `applying_from`/`district` reused verbatim — no `alteration_type`
# equivalent, since this service does exactly one thing (unlike
# amendment's 6 alteration types), and no domestic/overseas FORM split
# either (id=24 lists only one "Children Deletion"/"Form C" download —
# `applying_from` here only changes which OFFICE accepts it, same as
# amendment — see `app.seed.phase9_child_deletion`).
_child_deletion_age = next(q for q in RENEWAL_QUESTIONS if q[0] == "age")
_child_deletion_applying_from = next(q for q in RENEWAL_QUESTIONS if q[0] == "applying_from")
_child_deletion_district = next(q for q in RENEWAL_QUESTIONS if q[0] == "district")
# No `photo_district` here either — child-deletion has no "Photo studio
# acknowledgement" Requirement (confirmed against
# app.seed.phase9_child_deletion — no photo is taken to remove a name).
CHILD_DELETION_QUESTIONS: list[tuple[str, str, str, int, str | None]] = [
    (attribute, prompt, answer_type, index, hint)
    for index, (attribute, prompt, answer_type, _sequence, hint) in enumerate(
        (
            _child_deletion_age,
            _child_deletion_applying_from,
            _child_deletion_district,
        ),
        start=1,
    )
]

# Emergency Certificate (India and Nepal) — design.md service #7, the
# last of the seven. Shortest question set alongside child-deletion:
# `age` (still needed — gates the general 16-60 fingerprint requirement,
# id=7 seq 13, and the standard scope gate still applies here, unlike
# under-16), `applying_from`/`district` reused verbatim for the same
# domestic/overseas form-and-office split every other service has (the
# Overseas Missions form's own header literally includes "EMERGENCY/
# IDENTITY CERTIFICATE" — confirmed, not guessed). No `service_basis` —
# instructions_english_td.pdf (f)(ii) shows "–" for one-day service,
# i.e. no urgent tier exists for this document at all. No alteration-
# type/family-circumstance style question either — design.md is
# explicit that no source states a document list specific to this
# certificate beyond the K-35A form itself; this service's Requirements
# only include what's independently, generally sourced (the form,
# photo studio acknowledgement, fingerprints — all stated in unscoped
# "every applicant" language in id=7, not renewal-specific facts), not
# a copied-over adult document list. See `app.seed.phase9_emergency_
# certificate`.
_ec_age = next(q for q in RENEWAL_QUESTIONS if q[0] == "age")
_ec_applying_from = next(q for q in RENEWAL_QUESTIONS if q[0] == "applying_from")
_ec_district = next(q for q in RENEWAL_QUESTIONS if q[0] == "district")
_ec_photo_district = next(q for q in RENEWAL_QUESTIONS if q[0] == "photo_district")
EMERGENCY_CERTIFICATE_QUESTIONS: list[tuple[str, str, str, int, str | None]] = [
    (attribute, prompt, answer_type, index, hint)
    for index, (attribute, prompt, answer_type, _sequence, hint) in enumerate(
        (
            _ec_age,
            _ec_applying_from,
            _ec_district,
            _ec_photo_district,
        ),
        start=1,
    )
]

# Covers every question across every service — a single reverse-index
# dict any node/deterministic-matcher/classifier code can rely on,
# rather than each service's question list needing its own copy (a gap
# that silently dropped a classified `lost_passport_age` fact the first
# time this was written with ATTRIBUTE_BY_PROMPT built from
# RENEWAL_QUESTIONS alone — `lost_passport_age`'s prompt doesn't exist
# there at all).
ATTRIBUTE_BY_PROMPT: dict[str, str] = {
    prompt: attribute
    for attribute, prompt, _, _, _ in (
        *RENEWAL_QUESTIONS, *NEW_APPLICANT_QUESTIONS, *LOST_STOLEN_QUESTIONS,
        *AMENDMENT_QUESTIONS, *UNDER_16_QUESTIONS, *CHILD_DELETION_QUESTIONS,
        *EMERGENCY_CERTIFICATE_QUESTIONS,
    )
}
PROMPT_BY_ATTRIBUTE: dict[str, str] = {
    attribute: prompt for prompt, attribute in ATTRIBUTE_BY_PROMPT.items()
}


def is_relevant(db: Session, question: Question, answers: dict[str, str]) -> bool:
    """Whether a question is still relevant given answers so far.

    Two independent checks, both must pass:

    1. `section_19_2` is still special-cased in code — it only matters
       once `dual_citizen` is known to be true. This one predates the
       data-driven mechanism below and is left as-is (out of scope for
       the conditional-question-relevance work that added the second
       check).
    2. Any `QUESTION_CONDITION` rows linked to this question — the same
       flat, all-must-pass, each-optionally-negated shape
       `REQUIREMENT_CONDITION` already uses for requirements. A question
       with no linked conditions is unconditionally relevant here (this
       check is vacuously true), matching that same convention. This is
       what lets `buddhist_priest` be skipped by data (a seeded
       condition on `profession`) rather than by reordering questions in
       code — see the `renewal-rule-data` spec's "buddhist_priest
       question is data-gated" requirement.

    `condition_link_passes` treats a missing answer as "not satisfied"
    regardless of negation, so a negated condition on an attribute the
    citizen hasn't reached yet correctly stays not-relevant rather than
    guessing — not a practical concern for `buddhist_priest` specifically
    here, since `profession` (sequence 6) is always asked and answered
    before `buddhist_priest` (sequence 7) is ever reached, but the
    correct fail-safe regardless.
    """
    attribute = ATTRIBUTE_BY_PROMPT.get(question.prompt)
    if attribute == "section_19_2" and answers.get("dual_citizen") != "true":
        return False

    links = db.scalars(
        select(QuestionCondition).where(QuestionCondition.question_id == question.id)
    ).all()
    return all(
        condition_link_passes(link.condition, link.negated, answers) for link in links
    )
