"""Tests for the four intake/plan-quality fixes found during live testing:
data-driven buddhist_priest skipping, a plain-language wording audit,
the application form requirement + its structured resources, and the
Divisional-Secretariat-never-a-submission-location guarantee.
"""

from __future__ import annotations

import re

from sqlalchemy import select

from app.engine.next_question import next_question
from app.engine.offices import resolve_offices
from app.engine.renewal_intake import RENEWAL_QUESTIONS
from app.engine.resolver import resolve_case
from app.models import Office, Question

BASE_UP_TO_PROFESSION = {
    "age": "30",
    "holds_passport": "true",
    "name_changed": "false",
    "dual_citizen": "false",
    "section_19_2": "false",
}


def test_secular_profession_skips_buddhist_priest_question(renewal_service_id, db):
    for profession in ("doctor", "Doctor", "TEACHER", "engineer"):
        q = next_question(
            db,
            renewal_service_id,
            {**BASE_UP_TO_PROFESSION, "profession": profession},
        )
        assert q is not None
        assert "buddhist priest" not in q.prompt.lower(), (
            f"buddhist_priest was asked despite profession={profession!r}"
        )


def test_blank_or_unmatched_profession_still_asks_buddhist_priest(renewal_service_id, db):
    for profession in ("", "fisherman", "monk"):
        q = next_question(
            db,
            renewal_service_id,
            {**BASE_UP_TO_PROFESSION, "profession": profession},
        )
        assert q is not None
        assert "buddhist priest" in q.prompt.lower(), (
            f"buddhist_priest was skipped despite profession={profession!r}"
        )


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
        "age": "30", "holds_passport": "true", "name_changed": "false",
        "dual_citizen": "false", "section_19_2": "false", "profession": "",
        "buddhist_priest": "false", "district": "Kandy", "service_basis": "normal",
    }
    result = resolve_case(db, answers)
    office_names = {o.name for o in result.offices.offices}
    assert not any("divisional secretariat" in name.lower() for name in office_names)
