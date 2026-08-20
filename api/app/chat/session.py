"""6.10: persistent session memory.

CHAT_MESSAGE persistence, device-to-case resolution, transcript
retrieval, and a Redis hot-session cache-aside layer in front of it.
Postgres is always the durable record; Redis is a bounded-TTL fast path
that is never the only place a message or fact lives — every Redis call
here is wrapped so a cache failure degrades to reading Postgres
directly rather than surfacing as a citizen-facing error. See
design.md's "Postgres is truth, Redis is a cache, never the reverse"
decision.
"""

from __future__ import annotations

import json
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.redis_client import get_redis
from app.models import Case, CaseAnswer, ChatMessage, Question

# A few hours' TTL, per the plan — long enough to cover a citizen
# stepping away mid-intake, short enough that a stale cache never
# lingers meaningfully past an active session.
SESSION_TTL_SECONDS = 4 * 60 * 60


def record_message(
    db: Session,
    case_id: uuid.UUID,
    role: str,
    content: str,
    intent: str | None = None,
    cited_chunk_ids: list[str] | None = None,
    tool_trace: list[dict] | None = None,
) -> ChatMessage:
    """Persist one message (either direction) and invalidate that case's
    hot-session cache so the next read reflects it."""
    message = ChatMessage(
        case_id=case_id,
        role=role,
        content=content,
        intent=intent,
        cited_chunk_ids=cited_chunk_ids,
        tool_trace=tool_trace,
    )
    db.add(message)
    db.flush()
    _invalidate_session_cache(case_id)
    return message


def get_transcript(db: Session, case_id: uuid.UUID) -> list[ChatMessage]:
    """The full, ordered message history for a case — read straight from
    Postgres, the durable record."""
    return list(
        db.scalars(
            select(ChatMessage)
            .where(ChatMessage.case_id == case_id)
            .order_by(ChatMessage.created_at)
        ).all()
    )


def resolve_case_for_device(db: Session, device_ref: str) -> Case | None:
    """The device's most recent case that hasn't been resolved yet, if
    any — a returning citizen continues that case instead of starting a
    new one. "Most recent" is ordered by the case's latest message: a
    case only exists, on a later request, if at least one message was
    already recorded against it on an earlier one, so this needs no
    separate CASE.created_at column."""
    last_message_at = (
        select(func.max(ChatMessage.created_at))
        .where(ChatMessage.case_id == Case.id)
        .correlate(Case)
        .scalar_subquery()
    )
    return db.scalars(
        select(Case)
        .where(Case.device_ref == device_ref, Case.resolved_at.is_(None))
        .order_by(last_message_at.desc().nullslast())
        .limit(1)
    ).first()


def _serialize_message(message: ChatMessage) -> dict:
    return {
        "id": str(message.id),
        "role": message.role,
        "content": message.content,
        "created_at": message.created_at.isoformat(),
        "intent": message.intent,
        "cited_chunk_ids": message.cited_chunk_ids,
        "tool_trace": message.tool_trace,
    }


def _session_key(case_id: uuid.UUID) -> str:
    return f"govassist:case-session:{case_id}"


def cache_session(db: Session, case_id: uuid.UUID) -> None:
    """Cache-aside write: the case's full message transcript plus its
    answered facts, bounded TTL. Best-effort — see module docstring."""
    try:
        messages = get_transcript(db, case_id)
        answers = db.execute(
            select(Question.prompt, CaseAnswer.value)
            .join(Question, CaseAnswer.question_id == Question.id)
            .where(CaseAnswer.case_id == case_id)
        ).all()
        payload = json.dumps(
            {
                "messages": [_serialize_message(m) for m in messages],
                "answers": {prompt: value for prompt, value in answers},
            }
        )
        get_redis().set(_session_key(case_id), payload, ex=SESSION_TTL_SECONDS)
    except Exception:
        pass


def get_transcript_dicts(db: Session, case_id: uuid.UUID) -> list[dict]:
    """The transcript's hot path: Redis first, Postgres on a cache miss
    or a Redis failure — verified equivalent either way (see
    `tests/chat/test_session.py`'s "clearing Redis still restores the
    transcript" test)."""
    try:
        raw = get_redis().get(_session_key(case_id))
        if raw is not None:
            return json.loads(raw)["messages"]
    except Exception:
        pass
    return [_serialize_message(m) for m in get_transcript(db, case_id)]


def _invalidate_session_cache(case_id: uuid.UUID) -> None:
    try:
        get_redis().delete(_session_key(case_id))
    except Exception:
        pass
