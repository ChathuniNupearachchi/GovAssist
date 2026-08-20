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
    (
        "holds_passport",
        "Do you still hold your current or a previous passport?",
        "boolean",
        2,
        None,
    ),
    (
        "name_changed",
        "Has your name changed since your passport was issued?",
        "boolean",
        3,
        None,
    ),
    ("dual_citizen", "Are you a dual citizen?", "boolean", 4, None),
    (
        "section_19_2",
        "Did you apply for dual citizenship through the special "
        "provisions route, rather than the standard application?",
        "boolean",
        5,
        "Legal reference: section 19(2) of the Citizenship Act, "
        "as amended by Act No. 18 of 1948.",
    ),
    (
        "profession",
        "What is your job or occupation? (leave blank if you don't have one)",
        "single",
        6,
        None,
    ),
    ("buddhist_priest", "Are you a Buddhist priest?", "boolean", 7, None),
    ("district", "Which district are you applying from?", "district", 8, None),
    (
        "service_basis",
        "Do you need normal service, or urgent (same-day) service?",
        "single",
        9,
        None,
    ),
]

ATTRIBUTE_BY_PROMPT: dict[str, str] = {
    prompt: attribute for attribute, prompt, _, _, _ in RENEWAL_QUESTIONS
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
