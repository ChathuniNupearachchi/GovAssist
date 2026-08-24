"""Task 1.7 — compiles the `StateGraph` from the linear nodes, the
`agent`/`tools`/`verify` cycle, edges, and checkpointer; exposes the
two entry points `router.py` and `app/api/cases.py` call into.

Thread id: each call to `run_message_turn`/`run_resolve_action` uses a
freshly generated thread id (`f"{case_id}:{uuid4()}"`), not a thread id
shared across a case's turns. LangGraph's checkpointer resumes a
thread's *last* checkpointed state when given the same thread id again,
which would otherwise leak one turn's `agent_messages`/`tool_trace`
(turn-scoped by design — the model's tool-use conversation and trace
never span turns) into the next. A fresh thread id per turn keeps every
turn's initial state exactly what this module passes in, while the
checkpointer still records that turn's own step-by-step position for
inspection — satisfying "conversation position is checkpointed" without
importing state a new turn should not start with.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from app.chat.agent import ToolCallRecord
from app.chat.rephrase import rephrase_question
from app.chat.acknowledge import build_acknowledgement
from app.chat.session import get_transcript
from app.engine.renewal_intake import ATTRIBUTE_BY_PROMPT, RENEWAL_QUESTIONS
from app.engine.types import Citation
from app.graph.agent_nodes import agent_node, tools_node, verify_node
from app.graph.checkpointer import get_checkpointer
from app.graph.edges import (
    route_after_agent,
    route_after_next_question,
    route_after_tools,
    route_after_verify,
    route_entry,
)
from app.graph.nodes import classify_node, next_question_node, record_facts_node, resolve_node
from app.graph.state import GraphState
from app.models import Case, Question
from app.rag.answer import RAGResponse

_PROMPT_BY_ATTRIBUTE: dict[str, str] = {
    attribute: prompt for attribute, prompt, _, _, _ in RENEWAL_QUESTIONS
}

# Same as router.py's precedent — the last two turns for rephrasing's
# context, always ending with the citizen's current message.
_RECENT_TURNS_FOR_REPHRASING = 2


def build_graph() -> StateGraph:
    builder = StateGraph(GraphState)

    builder.add_node("classify", classify_node)
    builder.add_node("record_facts", record_facts_node)
    builder.add_node("next_question", next_question_node)
    builder.add_node("resolve", resolve_node)
    builder.add_node("agent", agent_node)
    builder.add_node("tools", tools_node)
    builder.add_node("verify", verify_node)

    builder.add_conditional_edges(START, route_entry, {"classify": "classify", "next_question": "next_question"})
    builder.add_edge("classify", "record_facts")
    builder.add_edge("record_facts", "next_question")
    builder.add_conditional_edges(
        "next_question", route_after_next_question, {"resolve": "resolve", "agent": "agent", END: END}
    )
    builder.add_edge("resolve", END)
    builder.add_conditional_edges(
        "agent", route_after_agent, {"tools": "tools", "verify": "verify", "agent": "agent", END: END}
    )
    builder.add_conditional_edges("tools", route_after_tools, {"agent": "agent", END: END})
    builder.add_conditional_edges("verify", route_after_verify, {"agent": "agent", END: END})

    return builder


_compiled = None


def get_compiled_graph():
    global _compiled
    if _compiled is None:
        _compiled = build_graph().compile(checkpointer=get_checkpointer())
    return _compiled


@dataclass(frozen=True)
class ChatOutcome:
    """Same shape as `app.chat.router.ChatOutcome` — the graph-backed
    replacement returns an identical interface so callers don't change."""

    rag_response: RAGResponse | None
    next_pending_question: Question | None
    intent: str | None
    acknowledgement: str | None = None
    next_question_display_text: str | None = None


def _recent_turn_contents(db: Session, case_id, current_message: str) -> list[str]:
    prior = get_transcript(db, case_id)[-(_RECENT_TURNS_FOR_REPHRASING - 1):]
    return [m.content for m in prior] + [current_message]


def run_message_turn(db: Session, case: Case, message: str) -> ChatOutcome:
    """Replaces `app.chat.router.handle_message` — invokes the compiled
    graph for one chat turn, then applies the same two presentation-only
    layers (acknowledgement, rephrasing) router.py already applied, since
    those never changed which question is asked or what gets recorded."""
    from app.chat.limits import truncate_message

    truncated = truncate_message(message)
    graph = get_compiled_graph()
    thread_id = f"{case.id}:{uuid.uuid4()}"

    result = graph.invoke(
        {"action": "message", "case_id": str(case.id), "message": truncated},
        config={"configurable": {"thread_id": thread_id, "db": db}},
    )

    rag_response: RAGResponse | None = None
    if result.get("should_answer_via_rag"):
        rag_answer = result.get("rag_answer")
        if rag_answer is None:
            rag_response = RAGResponse(text="I don't have that information.", citations=[], grounded=False)
        else:
            rag_response = RAGResponse(
                text=rag_answer["text"],
                citations=[
                    Citation(
                        source_document_id=uuid.UUID(c["source_document_id"]),
                        source_url=c["source_url"],
                        verified_at=c["verified_at"],
                    )
                    for c in rag_answer["citations"]
                ],
                grounded=True,
                cited_chunk_ids=rag_answer["cited_chunk_ids"],
                # RAGResponse.tool_trace's contract is list[ToolCallRecord]
                # (see app/rag/answer.py) — the graph's state only ever
                # holds plain JSON-safe dicts (checkpointer requirement),
                # so they're converted back to the dataclass here, at the
                # one point this leaves the graph, preserving the type
                # every existing caller (app/api/chat.py's asdict() call)
                # already relies on.
                tool_trace=[ToolCallRecord(**entry) for entry in rag_answer["trace"]],
            )

    answers_after = result.get("answers_after") or result.get("answers_before", {})
    acknowledgement = build_acknowledgement(
        db, result.get("extracted", {}), result.get("answers_before", {}), answers_after
    )

    next_pending_id = result.get("next_pending_question_id")
    next_pending = db.get(Question, uuid.UUID(next_pending_id)) if next_pending_id else None

    next_question_display_text = None
    if next_pending is not None:
        next_attribute = ATTRIBUTE_BY_PROMPT.get(next_pending.prompt)
        if next_attribute is not None:
            recent_turns = _recent_turn_contents(db, case.id, truncated)
            next_question_display_text = rephrase_question(next_pending.prompt, next_attribute, recent_turns)
        else:
            next_question_display_text = next_pending.prompt

    return ChatOutcome(
        rag_response=rag_response,
        next_pending_question=next_pending,
        intent=result.get("intent"),
        acknowledgement=acknowledgement,
        next_question_display_text=next_question_display_text,
    )


def run_resolve_action(db: Session, case_id: uuid.UUID) -> dict:
    """Replaces `app/api/cases.py::resolve`'s direct call to
    `app.engine.resolver.resolve_case` — invokes the compiled graph with
    `action="resolve"` and returns the same
    `{"ready": bool, ...}`-shaped dict `app/chat/tools.py::resolve_case`
    already produces, so the route's translation to `CaseResolutionOut`
    / `HTTPException` is unchanged."""
    graph = get_compiled_graph()
    thread_id = f"{case_id}:resolve:{uuid.uuid4()}"
    result = graph.invoke(
        {"action": "resolve", "case_id": str(case_id)},
        config={"configurable": {"thread_id": thread_id, "db": db}},
    )
    return result["resolution"]
