"""Top-level entry point for the open-question answering path.

Phase 5/6.7 built this as single-shot retrieve-then-generate; Phase
6.11 replaces the internals with `app.chat.agent`'s bounded tool-use
loop over the six system-capability tools (retrieval among them) — the
shape of `RAGResponse` is unchanged, and `answer_question` gains one new
optional `case_id` parameter so the agent can use case-scoped tools
(`get_next_question`, `resolve_case`, `compare_amendment_vs_renewal`)
without asking the citizen for an id it already has, mid-case.
`app.rag.retrieval.retrieve` and
`app.rag.generation.generate_answer` are unchanged in themselves; the
former is now `retrieve_documents`'s implementation, the latter is
unused by this path but still directly tested (`tests/rag/
test_generation.py`) as the pure function it always was.

RAG never produces a plan, fee, office, or checklist on its own —
`RAGResponse` is structurally incapable of carrying any of those
(contrast with `app.engine.types.CaseResolution`, the rules engine's
return type). The agent's tool-composed answers still only ever state a
fee/office/requirement value that traced to a tool call — see
`app.chat.agent`'s verification gate — so this remains true even though
the agent's tools include read-only engine calls.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.chat.agent import AgentAnswer, ToolCallRecord, answer_with_agent
from app.engine.types import Citation

NO_MATCH_TEXT = "I don't have that information."


@dataclass(frozen=True)
class RAGResponse:
    text: str
    citations: list[Citation]
    grounded: bool  # False only for the "no relevant match" response
    # 6.10: persisted onto CHAT_MESSAGE as the audit trail. Defaulted to
    # empty rather than made required, so existing call sites that
    # predate 6.10 (this module's own two callers above, and tests that
    # construct a RAGResponse directly) don't all need updating just to
    # add an empty list.
    cited_chunk_ids: list[str] = field(default_factory=list)
    # 6.11: the per-turn tool-call trace, persisted onto CHAT_MESSAGE
    # alongside cited_chunk_ids — None when the answer used no tools
    # (the "no relevant match" fallback).
    tool_trace: list[ToolCallRecord] | None = None


def answer_question(db: Session, query: str, case_id: str | None = None) -> RAGResponse:
    answer: AgentAnswer | None = answer_with_agent(db, query, case_id=case_id)
    if answer is None:
        # No tool-grounded answer could be produced — either nothing
        # relevant was found, or the agent's final answer failed
        # citation/value verification twice. Same explicit response
        # either way, so a citizen sees one consistent failure mode.
        return RAGResponse(text=NO_MATCH_TEXT, citations=[], grounded=False)
    return RAGResponse(
        text=answer.text,
        citations=answer.citations,
        grounded=True,
        cited_chunk_ids=answer.cited_chunk_ids,
        tool_trace=answer.trace,
    )
