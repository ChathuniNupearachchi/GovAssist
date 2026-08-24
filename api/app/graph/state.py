"""Task 1.2 — the graph's state shape.

Deliberately holds no `db: Session` — a SQLAlchemy session is
per-request, not serializable, and must never be checkpointed. Every
node reads it from `config["configurable"]["db"]` instead (set once at
`.invoke()`/`.stream()` time by the caller — see `build.py`), exactly
the pattern LangGraph's own docs use for injecting a request-scoped
resource. Only the conversational/business state below is part of
`GraphState`, so it's the only thing the Postgres checkpointer persists
— see the graph-orchestration spec's "conversation position is
checkpointed independently of case facts" requirement: none of these
fields duplicate a `CASE_ANSWER` row, they only track where in the graph
this turn currently is.

Two entry paths share this graph (design.md's "two entry paths sharing
next_question" decision):
  - `action="message"`: a chat turn — classify/record_facts/next_question,
    then the agent/tools/verify cycle if the message asked a question.
  - `action="resolve"`: `POST /case/{id}/resolve` — next_question's
    readiness check, then `resolve`. No citizen message on this path.
"""

from __future__ import annotations

from typing import Any, Literal, TypedDict


class ToolCallRecordDict(TypedDict):
    tool: str
    arguments: dict[str, Any]
    result: dict[str, Any]


class GraphState(TypedDict, total=False):
    # --- Set by the caller before invoking the graph ---
    action: Literal["message", "resolve"]
    case_id: str
    service_id: str
    message: str  # truncated citizen message; unused for action="resolve"

    # --- classify / record_facts ---
    pending_attribute: str | None
    intent: str | None
    extracted: dict[str, str]
    contains_question: bool
    should_answer_via_rag: bool
    answers_before: dict[str, str]
    answers_after: dict[str, str]

    # --- agent / tools / verify cycle (action="message" only) ---
    agent_messages: list[dict[str, Any]]  # Anthropic message-format history
    tool_trace: list[ToolCallRecordDict]
    chunk_lookup: dict[str, dict[str, Any]]
    fee_values: list[float]
    office_names: list[str]
    requirement_labels: list[str]
    tool_iterations: int
    verification_retries: int
    truncation_retries: int
    no_tool_call_retries: int
    pending_tool_calls: list[dict[str, Any]]  # tool_use blocks awaiting execution
    pending_submission: dict[str, Any] | None  # submit_answer block awaiting verify
    verification_error: str | None
    rag_answer: dict[str, Any] | None  # AgentAnswer-shaped dict, or None
    # Explicit routing signal set by every agent/tools/verify node —
    # edges.py reads this directly rather than inferring intent from
    # which other fields did or didn't change, which is ambiguous once
    # a field like `rag_answer` can legitimately be None either because
    # nothing has run yet or because this cycle terminally failed.
    next_step: Literal["agent", "tools", "verify", "end"]

    # --- next_question / resolve (both action values) ---
    next_pending_question_id: str | None
    next_pending_question_prompt: str | None
    resolution: dict[str, Any] | None  # resolve_case-shaped dict (action="resolve")

    # --- presentation-only, action="message" ---
    acknowledgement: str | None
    next_question_display_text: str | None
