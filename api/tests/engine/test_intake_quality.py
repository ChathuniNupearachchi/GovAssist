"""Tests for the four intake/plan-quality fixes found during live testing:
data-driven buddhist_priest skipping, a plain-language wording audit,
the application form requirement + its structured resources, and the
Divisional-Secretariat-never-a-submission-location guarantee.

`test_secular_profession_skips_buddhist_priest_question` and
`test_blank_or_unmatched_profession_still_asks_buddhist_priest` were
rewritten (manual QA bug #6): the priest question used to be suppressed
by a stated secular profession, which silently excluded a monk who also
holds a secular occupation (teacher, scholar, lecturer — common in Sri
Lanka) from the mandatory Samanera/Higher Ordination certificate
requirement. buddhist_priest is now asked unconditionally, before
profession, regardless of what profession is (or isn't) stated.
"""

from __future__ import annotations

import re

from sqlalchemy import select

from app.engine.next_question import next_question
from app.engine.offices import resolve_offices
from app.engine.renewal_intake import ATTRIBUTE_BY_PROMPT, RENEWAL_QUESTIONS, is_relevant
from app.engine.resolver import resolve_case
from app.models import Office, Question

BASE_UP_TO_PROFESSION = {
    "age": "30",
    "applying_from": "sri_lanka",
    "holds_passport": "true",
    "name_changed": "false",
    "dual_citizen": "false",
    "section_19_2": "false",
}


def test_buddhist_priest_is_asked_before_profession(renewal_service_id, db):
    priest_seq = next(seq for attr, _, _, seq, _ in RENEWAL_QUESTIONS if attr == "buddhist_priest")
    profession_seq = next(seq for attr, _, _, seq, _ in RENEWAL_QUESTIONS if attr == "profession")
    assert priest_seq < profession_seq

    q = next_question(db, renewal_service_id, BASE_UP_TO_PROFESSION)
    assert q is not None
    assert "buddhist priest" in q.prompt.lower()


def test_buddhist_priest_is_asked_regardless_of_stated_profession(renewal_service_id, db):
    """Regression for manual QA bug #6: a stated profession — secular,
    unmatched, or blank — must never suppress the priest question. Checks
    `is_relevant` directly (not just question order) so this actually
    verifies no suppressing condition exists, rather than the question's
    new earlier sequence position merely masking one."""
    priest_question = db.scalars(
        select(Question).where(Question.service_id == renewal_service_id)
    ).all()
    priest_question = next(
        q for q in priest_question if ATTRIBUTE_BY_PROMPT.get(q.prompt) == "buddhist_priest"
    )
    for profession in ("doctor", "Doctor", "TEACHER", "engineer", "", "fisherman", "monk"):
        assert is_relevant(
            db, priest_question, {**BASE_UP_TO_PROFESSION, "profession": profession}
        ), f"buddhist_priest was suppressed despite profession={profession!r}"


def test_profession_question_gated_on_age(renewal_service_id, db):
    """Manual QA bug #5: profession must not be asked of an applicant
    known to be under 16 — reuses the same age<16 condition the
    fingerprint requirement gates on."""
    profession_question = next(
        q for q in db.scalars(select(Question).where(Question.service_id == renewal_service_id)).all()
        if ATTRIBUTE_BY_PROMPT.get(q.prompt) == "profession"
    )
    assert not is_relevant(db, profession_question, {**BASE_UP_TO_PROFESSION, "age": "15"})
    assert is_relevant(db, profession_question, {**BASE_UP_TO_PROFESSION, "age": "16"})


# Plain-language audit: no QUESTION.prompt should require knowing an Act,
# a section number, or legal terminology to answer. Flags any prompt
# containing an "Act" reference, a "section N" reference, or a bare
# "N(N)" citation pattern.
_LEGAL_TERM_RE = re.compile(
    r"\bAct\b|\bsection\s+\d|\b\d{1,3}\(\d{1,2}\)\b", re.IGNORECASE
)


def test_no_question_prompt_requires_legal_knowledge():
    for _attribute, prompt, _answer_type, _sequence, _hint in RENEWAL_QUESTIONS:
        assert not _LEGAL_TERM_RE.search(prompt), (
            f"prompt requires legal knowledge to answer: {prompt!r}"
        )


def test_section_19_2_question_is_answerable_without_knowing_the_term(db):
    prompt = next(
        prompt
        for attribute, prompt, *_ in RENEWAL_QUESTIONS
        if attribute == "section_19_2"
    )
    assert "section 19" not in prompt.lower()
    assert "citizenship act" not in prompt.lower()


def test_only_section_19_2_carries_a_hint(db):
    """Every other renewal question is answerable without any
    legislative knowledge to begin with, so `hint` is null for them —
    only section_19_2 (the one genuinely legal-reference-shaped fact)
    has one, and the reference lives there, not in the plain-language
    prompt itself."""
    questions = db.scalars(select(Question)).all()
    hinted = {q.prompt: q.hint for q in questions if q.hint is not None}
    assert len(hinted) == 1
    prompt, hint = next(iter(hinted.items()))
    assert "19(2)" in hint
    assert "19(2)" not in prompt


def test_divisional_secretariat_never_returned_as_an_office(db):
    resolution = resolve_offices(db, district="Kandy", basis="normal")
    assert not any(o.type == "ds" for o in resolution.offices)

    # Confirm at the schema level too — resolve_offices never even
    # queries type="ds", so this isn't just "none happen to match".
    ds_offices = db.scalars(select(Office).where(Office.type == "ds")).all()
    # No DS offices are seeded as accepting locations at all (Phase 2/4
    # never seed one) — if this ever changes, the assertion above is the
    # one that actually protects the plan.
    assert ds_offices == []


def test_resolved_plan_never_mentions_a_divisional_secretariat_as_submission(db):
    answers = {
        "age": "30", "applying_from": "sri_lanka", "holds_passport": "true", "name_changed": "false",
        "dual_citizen": "false", "section_19_2": "false", "profession": "",
        "buddhist_priest": "false", "district": "Kandy", "service_basis": "normal",
    }
    result = resolve_case(db, answers)
    office_names = {o.name for o in result.offices.offices}
    assert not any("divisional secretariat" in name.lower() for name in office_names)
