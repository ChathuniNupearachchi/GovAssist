"""6.1 Router — ties the deterministic pass, the Claude classifier, the
rules engine, and RAG together into one chat turn. 6.11 adds two
presentation-only layers around the same flow: a visible acknowledgement
of what was just recorded, and a contextually rephrased next question —
neither changes what gets recorded or which question is asked next.

Every classification outcome — a deterministic match, or a Claude
classification with any combination of `intent`/`contains_question` —
reduces to two independent actions that may both fire in the same turn:
record any extracted facts as `CaseAnswer` rows, and answer via RAG if
the message contains a question. This is why a combined
situation+question message needs no special case; see design.md's
"`/chat/message` routes intent uniformly through 'record' and 'answer'"
decision.

Case state (extracted facts) lives in CASE_ANSWER, not in conversation
history, per CLAUDE.md's device-only storage model — this module never
holds state across calls itself.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.chat.acknowledge import build_acknowledgement
from app.chat.classifier import classify
from app.chat.deterministic import try_deterministic_match
from app.chat.limits import truncate_message
from app.chat.rephrase import rephrase_question
from app.chat.session import get_transcript
from app.engine.next_question import next_question
from app.engine.renewal_intake import ATTRIBUTE_BY_PROMPT, RENEWAL_QUESTIONS
from app.models import Case, CaseAnswer, Question
from app.rag.answer import RAGResponse, answer_question

_PROMPT_BY_ATTRIBUTE: dict[str, str] = {
    attribute: prompt for attribute, prompt, _, _, _ in RENEWAL_QUESTIONS
}

# How many of the case's most recent prior messages rephrasing sees for
# context — "the last two turns" per the request.
_RECENT_TURNS_FOR_REPHRASING = 2


@dataclass(frozen=True)
class ChatOutcome:
    rag_response: RAGResponse | None
    next_pending_question: Question | None
    # 6.10: persisted onto the user's CHAT_MESSAGE row as part of the
    # audit trail — "answer" for a deterministic match (a bare answer
    # token is never classified), otherwise the classifier's own intent.
    intent: str | None
    # 6.11.3: acknowledgement of exactly the facts recorded this turn,
    # or None when nothing was recorded (or acknowledgement generation
    # failed — presentation only, never blocks the turn).
    acknowledgement: str | None = None
    # 6.11.2: `next_pending_question.prompt`'s rephrased surface text —
    # always about the same attribute; falls back to the canonical
    # prompt on a mismatch or generation failure. None when there is no
    # pending question.
    next_question_display_text: str | None = None


def _answers_dict(db: Session, case_id) -> dict[str, str]:
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


def _record_answer(db: Session, case: Case, attribute: str, value: str) -> None:
    prompt = _PROMPT_BY_ATTRIBUTE.get(attribute)
    if prompt is None:
        # Not one of the renewal intake's known attributes — nothing to
        # record it against.
        return
    question = db.scalars(
        select(Question).where(
            Question.service_id == case.service_id, Question.prompt == prompt
        )
    ).first()
    if question is None:
        return

    existing = db.scalars(
        select(CaseAnswer).where(
            CaseAnswer.case_id == case.id, CaseAnswer.question_id == question.id
        )
    ).first()
    if existing is not None:
        existing.value = value
    else:
        db.add(CaseAnswer(case_id=case.id, question_id=question.id, value=value))
    db.flush()


def _recent_turn_contents(db: Session, case_id, current_message: str) -> list[str]:
    """The most recent turns for rephrasing's context — always ends with
    the citizen's current message. Without this, the very message that
    usually carries the context rephrasing needs ("I want to renew my
    passport", "I need a passport for my daughter") would never reach
    it: it triggered this turn but isn't persisted as a ChatMessage
    until after `handle_message` returns (see `app/api/chat.py`), so
    reading only already-persisted history left every first-message
    rephrasing with nothing to work with — confirmed directly by tracing
    calls across a live conversation before this fix."""
    prior = get_transcript(db, case_id)[-(_RECENT_TURNS_FOR_REPHRASING - 1):]
    return [m.content for m in prior] + [current_message]


def handle_message(db: Session, case: Case, message: str) -> ChatOutcome:
    """Truncate -> deterministic pass -> (if no match) Claude classify ->
    record extracted facts -> acknowledge them -> answer via RAG if a
    question was asked -> compute and (possibly) rephrase the next
    question."""
    truncated = truncate_message(message)

    answers_before = _answers_dict(db, case.id)
    pending = next_question(db, case.service_id, answers_before)
    pending_attribute = (
        ATTRIBUTE_BY_PROMPT.get(pending.prompt) if pending is not None else None
    )

    extracted: dict[str, str] = {}
    contains_question = False
    should_answer_via_rag = False

    deterministic_value = None
    if pending_attribute is not None:
        deterministic_value = try_deterministic_match(pending_attribute, truncated)

    intent: str | None
    if deterministic_value is not None:
        extracted[pending_attribute] = deterministic_value
        intent = "answer"
        # A bare answer token is never itself a question — no Claude
        # call, no RAG call.
    else:
        classification = classify(
            truncated, pending.prompt if pending is not None else None
        )
        for attribute, value in classification.extracted.model_dump().items():
            if value is not None:
                extracted[attribute] = value
        contains_question = classification.contains_question
        should_answer_via_rag = (
            contains_question or classification.intent == "question"
        )
        intent = classification.intent

    for attribute, value in extracted.items():
        _record_answer(db, case, attribute, value)

    answers_after = _answers_dict(db, case.id)
    acknowledgement = build_acknowledgement(db, extracted, answers_before, answers_after)

    rag_response: RAGResponse | None = None
    if should_answer_via_rag:
        rag_response = answer_question(db, truncated, case_id=str(case.id))

    next_pending = next_question(db, case.service_id, answers_after)

    next_question_display_text = None
    if next_pending is not None:
        next_attribute = ATTRIBUTE_BY_PROMPT.get(next_pending.prompt)
        if next_attribute is not None:
            recent_turns = _recent_turn_contents(db, case.id, truncated)
            next_question_display_text = rephrase_question(
                next_pending.prompt, next_attribute, recent_turns
            )
        else:
            next_question_display_text = next_pending.prompt

    return ChatOutcome(
        rag_response=rag_response,
        next_pending_question=next_pending,
        intent=intent,
        acknowledgement=acknowledgement,
        next_question_display_text=next_question_display_text,
    )
