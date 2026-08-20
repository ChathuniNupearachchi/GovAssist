"""6.3 GET /case/{id}/next-question, POST /case/{id}/resolve.

`resolve` assembles the case's `CaseAnswer` rows into the same
`{attribute: value}` dict shape the engine already expects (via the same
`ATTRIBUTE_BY_PROMPT` reverse-lookup `next_question.py` uses), checks
`next_question` first, and returns a "not ready" 409 naming the pending
question rather than letting `resolve_case`'s `ValueError` (on a missing
`age`) leak through as an unhandled 500 — see design.md's "`/case/{id}/
resolve` does not itself drive intake" decision.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import CaseResolutionOut, QuestionOut
from app.db.session import get_db
from app.engine.next_question import next_question
from app.engine.renewal_intake import ATTRIBUTE_BY_PROMPT
from app.engine.resolver import resolve_case
from app.engine.types import IncompleteCaseError
from app.models import Case, CaseAnswer, Question

router = APIRouter(prefix="/case", tags=["cases"])


def _get_case(db: Session, case_id: uuid.UUID) -> Case:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


def _answers_dict(db: Session, case_id: uuid.UUID) -> dict[str, str]:
    rows = db.execute(
        select(CaseAnswer.value, Question.prompt)
        .join(Question, CaseAnswer.question_id == Question.id)
        .where(CaseAnswer.case_id == case_id)
    ).all()
    answers: dict[str, str] = {}
    for value, prompt in rows:
        attribute = ATTRIBUTE_BY_PROMPT.get(prompt)
        if attribute is not None:
            answers[attribute] = value
    return answers


@router.get("/{case_id}/next-question", response_model=QuestionOut | None)
def get_next_question(
    case_id: uuid.UUID, db: Session = Depends(get_db)
) -> QuestionOut | None:
    case = _get_case(db, case_id)
    question = next_question(db, case.service_id, _answers_dict(db, case_id))
    if question is None:
        return None
    return QuestionOut(
        id=question.id,
        prompt=question.prompt,
        answer_type=question.answer_type,
        # This route doesn't run 6.11.2's rephrasing (that's the chat
        # turn's job) — display_text is the canonical prompt here.
        display_text=question.prompt,
        hint=question.hint,
    )


def _is_under_16(answers: dict[str, str]) -> bool:
    age = answers.get("age")
    return age is not None and float(age) < 16


@router.post("/{case_id}/resolve", response_model=CaseResolutionOut)
def resolve(case_id: uuid.UUID, db: Session = Depends(get_db)) -> CaseResolutionOut:
    case = _get_case(db, case_id)
    answers = _answers_dict(db, case_id)

    # Age is evaluated first, unconditionally, mirroring resolve_case's
    # own precedence (see app.engine.resolver's docstring) — an
    # under-16 case short-circuits to the scope-gate response as soon
    # as age is known, without waiting on the rest of intake. Every
    # other case still needs the full intake before it's "ready".
    if not _is_under_16(answers):
        pending = next_question(db, case.service_id, answers)
        if pending is not None:
            raise HTTPException(
                status_code=409,
                detail=f"Case is not ready to resolve — still pending: {pending.prompt}",
            )

    # The pending-question check above already blocks an incomplete case
    # from reaching here; this catch is a backstop, not the primary
    # guard — `resolve_case` enforces the same completeness rule
    # internally (see its docstring), so the two can never disagree in
    # normal operation, but a caller should never rely solely on its own
    # pre-check when the engine itself refuses to guess.
    try:
        resolution = resolve_case(db, answers)
    except IncompleteCaseError as exc:
        raise HTTPException(
            status_code=409,
            detail=f"Case is not ready to resolve — still pending: {exc.pending_prompt}",
        ) from exc

    # 6.10: marks the case resolved so device-to-case resolution
    # (app.chat.session.resolve_case_for_device) stops resuming it — a
    # citizen who already has a completed plan starts a fresh case next
    # time, rather than being stuck "continuing" a finished one.
    case.resolved_at = datetime.now(timezone.utc)
    db.commit()

    return CaseResolutionOut.from_resolution(resolution)
