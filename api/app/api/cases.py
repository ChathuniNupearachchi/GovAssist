"""6.3 GET /case/{id}/next-question, POST /case/{id}/resolve.

`resolve` (task 1.9 of `langgraph-orchestration-branch`) now invokes the
compiled graph's `action="resolve"` path (`app.graph.build.
run_resolve_action`) instead of calling `app.engine.resolver.resolve_case`
directly — the graph's `next_question`/`resolve` nodes reproduce the
exact same readiness check and age-first precedence this route
previously implemented inline (see design.md's "two entry paths sharing
next_question" decision). The route's HTTP contract (404/409/200
shapes) is unchanged.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import CaseResolutionOut, QuestionOut
from app.db.session import get_db
from app.engine.next_question import next_question
from app.engine.renewal_intake import ATTRIBUTE_BY_PROMPT
from app.graph.build import run_resolve_action
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


@router.post("/{case_id}/resolve", response_model=CaseResolutionOut)
def resolve(case_id: uuid.UUID, db: Session = Depends(get_db)) -> CaseResolutionOut:
    _get_case(db, case_id)  # 404 if the case doesn't exist

    # The graph's `next_question` node (action="resolve") does the same
    # age-first-then-readiness check this route used to do inline, and
    # its `resolve` node does the same `resolve_case` call plus the
    # `case.resolved_at` commit — see design.md's "two entry paths
    # sharing next_question" decision.
    result = run_resolve_action(db, case_id)

    if not result.get("ready", False):
        raise HTTPException(
            status_code=409,
            detail=f"Case is not ready to resolve — still pending: {result.get('pending_question')}",
        )

    return CaseResolutionOut.from_resolution_dict(result)
