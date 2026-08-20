"""4.6 Next-question logic.

Given a case's currently recorded answers, returns the next Question the
resolver still needs — the next one in sequence that (a) has no recorded
answer and (b) is still relevant given what's already known. Relevance
combines a code special-case (`section_19_2`, only relevant once
`dual_citizen` is `true`) with any seeded `QUESTION_CONDITION` rows
(e.g. `buddhist_priest`, skipped when `profession` already indicates a
secular occupation) — see `app.engine.renewal_intake.is_relevant`. The
selection algorithm itself — iterate in sequence, return the first
unanswered-and-relevant question — is unchanged; only what "relevant"
consults grew a data-driven source.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.engine.renewal_intake import ATTRIBUTE_BY_PROMPT, is_relevant
from app.models import Question


def next_question(
    db: Session, service_id: uuid.UUID, answers: dict[str, str]
) -> Question | None:
    """Return the next unanswered, still-relevant Question, or None once
    every relevant question has an answer."""
    questions = db.scalars(
        select(Question)
        .where(Question.service_id == service_id)
        .order_by(Question.sequence)
    ).all()

    for question in questions:
        attribute = ATTRIBUTE_BY_PROMPT.get(question.prompt)
        if attribute is None:
            # Not one of the renewal intake's known questions — surface
            # it rather than silently skip, since we have no basis to
            # judge relevance for an unrecognized question.
            return question
        if attribute in answers:
            continue
        if is_relevant(db, question, answers):
            return question
    return None
