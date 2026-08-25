"""Task 1.5 — deterministic conditional-edge functions.

Every routing decision here reads plain state fields set by a prior
node (`state["action"]`, `state["should_answer_via_rag"]`,
`state["next_step"]`) — never a value parsed out of model output. See
the graph-orchestration spec's "Graph routing is deterministic, never
model-selected" requirement.
"""

from __future__ import annotations

from langgraph.graph import END

from app.graph.state import GraphState


def route_entry(state: GraphState) -> str:
    """`action="message"` starts at `classify`; `action="resolve"` skips
    straight to `next_question` (its readiness/under-16 check) — there
    is no citizen message to classify or facts to record on that path."""
    return "classify" if state["action"] == "message" else "next_question"


def route_after_next_question(state: GraphState) -> str:
    if state["action"] == "resolve":
        return "resolve"
    if state.get("scope_gate_message") or state.get("greeting_message"):
        # Under-16 just got recorded this turn, or the message was a
        # greeting/orientation request — end immediately with that
        # message rather than also answering an open question the same
        # message happened to ask (see next_question_node).
        return END
    if state.get("should_answer_via_rag"):
        return "agent"
    return END


def route_after_agent(state: GraphState) -> str:
    next_step = state["next_step"]
    if next_step == "tools":
        return "tools"
    if next_step == "verify":
        return "verify"
    if next_step == "agent":
        return "agent"
    return END


def route_after_tools(state: GraphState) -> str:
    return END if state["next_step"] == "end" else "agent"


def route_after_verify(state: GraphState) -> str:
    return "agent" if state["next_step"] == "agent" else END
