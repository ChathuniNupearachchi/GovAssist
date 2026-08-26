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
    (
        "service_basis",
        "Do you need normal service, or urgent (same-day) service?",
        "single",
        10,
        None,
    ),
]

# New passport (first-time applicant) — design.md service #2: "same
# documents/fee/form as renewal, different citizen framing," so this
# reuses RENEWAL_QUESTIONS' exact attribute vocabulary and prompt
# wording (kept in ATTRIBUTE_BY_PROMPT/next_question/deterministic.py
# unchanged — no new question text to maintain in three places) rather
# than a hand-duplicated list that could silently drift from renewal's.
# The one structural difference: no `holds_passport` question at all —
# a first-time applicant has no prior passport to hold by definition,
# so there's no fact to ask and no CURRENT_PASSPORT-equivalent document
# Requirement (see `app.seed.phase9_new_applicant`). Sequence renumbered
# contiguously after removing it.
NEW_APPLICANT_QUESTIONS: list[tuple[str, str, str, int, str | None]] = [
    (attribute, prompt, answer_type, index, hint)
    for index, (attribute, prompt, answer_type, _sequence, hint) in enumerate(
        (q for q in RENEWAL_QUESTIONS if q[0] != "holds_passport"),
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
