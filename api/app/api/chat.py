"""6.3 POST /chat/message + 6.10 device-based case resolution and
message persistence.

Creates a case when none is referenced (`device_ref` required in that
case — `Case.device_ref` is `NOT NULL`, per CLAUDE.md's device-only
storage model). When `case_id` is omitted but `device_ref` matches an
existing, unresolved case, that case is resumed instead of a new one
being created — a returning citizen continues their conversation rather
than starting over silently. Every inbound and outbound message is
persisted (6.10.1), and the case's hot session is refreshed in Redis
after each turn.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import (
    ChatMessageResponse,
    QuestionOut,
    RAGAnswerOut,
    TranscriptOut,
)
from app.chat.router import handle_message
from app.chat.session import (
    cache_session,
    get_transcript_dicts,
    record_message,
    resolve_case_for_device,
)
from app.db.session import get_db
from app.engine.resolver import RENEWAL_SERVICE_CODE
from app.models import Case, Service

router = APIRouter(tags=["chat"])


class ChatMessageRequest(BaseModel):
    message: str
    case_id: uuid.UUID | None = None
    device_ref: str | None = None


def _get_or_create_case(db: Session, body: ChatMessageRequest) -> Case:
    if body.case_id is not None:
        case = db.get(Case, body.case_id)
        if case is None:
            raise HTTPException(status_code=404, detail="Case not found")
        return case

    if not body.device_ref:
        raise HTTPException(
            status_code=422,
            detail="device_ref is required when case_id is omitted",
        )

    # 6.10: a returning device resumes its most recent unresolved case
    # rather than starting a new one every time case_id is omitted.
    existing = resolve_case_for_device(db, body.device_ref)
    if existing is not None:
        return existing

    service = db.scalars(
        select(Service).where(Service.code == RENEWAL_SERVICE_CODE)
    ).first()
    if service is None:
        raise HTTPException(
            status_code=500, detail="passport-renewal service is not seeded"
        )
    case = Case(service_id=service.id, device_ref=body.device_ref)
    db.add(case)
    db.flush()
    return case


@router.post("/chat/message", response_model=ChatMessageResponse)
def post_chat_message(
    body: ChatMessageRequest, db: Session = Depends(get_db)
) -> ChatMessageResponse:
    case = _get_or_create_case(db, body)

    outcome = handle_message(db, case, body.message)

    record_message(db, case.id, role="user", content=body.message, intent=outcome.intent)
    if outcome.acknowledgement is not None:
        record_message(db, case.id, role="assistant", content=outcome.acknowledgement)
    if outcome.rag_response is not None:
        tool_trace = (
            [asdict(record) for record in outcome.rag_response.tool_trace]
            if outcome.rag_response.tool_trace
            else None
        )
        record_message(
            db,
            case.id,
            role="assistant",
            content=outcome.rag_response.text,
            cited_chunk_ids=outcome.rag_response.cited_chunk_ids or None,
            tool_trace=tool_trace,
        )

    db.commit()
    cache_session(db, case.id)

    next_question_out = None
    if outcome.next_pending_question is not None:
        next_question_out = QuestionOut(
            id=outcome.next_pending_question.id,
            prompt=outcome.next_pending_question.prompt,
            answer_type=outcome.next_pending_question.answer_type,
            display_text=outcome.next_question_display_text or outcome.next_pending_question.prompt,
            hint=outcome.next_pending_question.hint,
        )

    return ChatMessageResponse(
        case_id=case.id,
        answer=(
            RAGAnswerOut.from_response(outcome.rag_response)
            if outcome.rag_response is not None
            else None
        ),
        next_question=next_question_out,
        acknowledgement=outcome.acknowledgement,
    )


@router.get("/chat/transcript", response_model=TranscriptOut)
def get_transcript(
    device_ref: str, db: Session = Depends(get_db)
) -> TranscriptOut:
    """6.10.4: restores a device's active-case conversation on reopen —
    not just the engine's resolved facts, the visible transcript too. A
    device with no prior case gets an empty transcript, not an error."""
    case = resolve_case_for_device(db, device_ref)
    if case is None:
        return TranscriptOut(case_id=None, messages=[])
    return TranscriptOut(case_id=case.id, messages=get_transcript_dicts(db, case.id))
