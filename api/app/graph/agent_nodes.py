"""Task 1.4 — the `agent` / `tools` / `verify` tool-calling cycle.

LangGraph's standard tool-calling cycle, replacing `app.chat.agent
.answer_with_agent`'s `while True` loop with graph nodes + edges (see
design.md's revised Decision) — but reusing that module's constants,
system prompt, tool schemas, and pure verification/citation-building
helpers directly rather than duplicating them. `app.chat.agent` itself
is untouched and stays directly tested by `tests/chat/test_agent.py` —
this module only adds the graph wiring around the same logic.

Simplification versus the original loop, noted here per the user's
"report any golden scenario whose output differs from main" instruction:
the original loop lets a single model turn include both regular tool
calls and a `submit_answer` call together, executing the regular calls
and then verifying the submission in the same iteration. This graph
instead routes a turn to `tools` whenever it contains any non-submit
tool call — a co-occurring `submit_answer` in that same turn is not
acted on that iteration; the model gets the tool results back and, in
the observed common case (the system prompt frames `submit_answer` as
the terminal action), calls `submit_answer` again cleanly on a later
turn. This only changes behavior for a turn that mixes both, which
`golden-parity` testing (task 1.8) checks for directly.
"""

from __future__ import annotations

import json
from typing import Any

import anthropic
from langchain_core.runnables import RunnableConfig
from sqlalchemy.orm import Session

from app.chat.agent import (
    ALL_SCHEMAS,
    CASE_INDEPENDENT_SCHEMAS,
    MAX_TOKENS,
    MAX_TOOL_ITERATIONS,
    MAX_VERIFICATION_RETRIES,
    MODEL,
    SYSTEM_PROMPT,
    TOOL_SCHEMAS,
    _build_citations,
    _build_initial_message,
    _collect_seen_values,
    _verify_submission,
)
from app.chat.tools import call_tool
from app.graph.state import GraphState
from app.observability.tracing import traced_generation, traced_node, traced_tool


def _get_db(config: RunnableConfig) -> Session:
    return config["configurable"]["db"]


def _block_to_dict(block: Any) -> dict[str, Any]:
    """`response.content`'s blocks are Anthropic SDK Pydantic objects —
    not JSON/msgpack-serializable, so they can't go straight into
    checkpointed state (`agent_messages`) the way the original in-memory
    `while` loop in `app.chat.agent` passed them around. Anthropic's API
    accepts plain dicts back as message content just as well as its own
    typed objects, so converting once here, immediately after receiving
    a response, both fixes checkpointing and keeps every later
    `client.messages.create()` call working unchanged."""
    if hasattr(block, "model_dump"):
        return block.model_dump()
    return dict(vars(block))


@traced_node("agent")
def agent_node(state: GraphState, config: RunnableConfig) -> dict[str, Any]:
    """One model turn: decide to call a tool, or submit a final answer."""
    messages = state.get("agent_messages")
    if not messages:
        messages = [
            {
                "role": "user",
                "content": _build_initial_message(state["message"], state.get("case_id")),
            }
        ]

    client = anthropic.Anthropic()
    try:
        if len(messages) == 1:
            # First turn: force a real tool call — `tools` excludes
            # submit_answer and `tool_choice` requires one of them, so
            # the model cannot decline (plain text) or submit a final
            # answer without having tried anything first. See
            # `app.chat.agent.answer_with_agent`'s identical fix and its
            # comment for why — observed directly that the same query
            # sometimes answered correctly and sometimes refused
            # outright with zero tool calls, run to run. Restricted to
            # case-independent tools when no case_id is known, same
            # reasoning as that fix's case_id branch.
            first_turn_schemas = TOOL_SCHEMAS if state.get("case_id") else CASE_INDEPENDENT_SCHEMAS
            with traced_generation("agent_turn_0", MODEL, messages) as gen:
                response = client.messages.create(
                    model=MODEL,
                    max_tokens=MAX_TOKENS,
                    system=SYSTEM_PROMPT,
                    tools=first_turn_schemas,
                    tool_choice={"type": "any"},
                    messages=messages,
                )
                gen.update(output={"stop_reason": response.stop_reason})
        else:
            with traced_generation("agent_turn", MODEL, messages) as gen:
                response = client.messages.create(
                    model=MODEL,
                    max_tokens=MAX_TOKENS,
                    system=SYSTEM_PROMPT,
                    tools=ALL_SCHEMAS,
                    messages=messages,
                )
                gen.update(output={"stop_reason": response.stop_reason})
    except Exception:
        # API failure during tool selection — same explicit no-relevant-
        # match fallback as any other failure to produce a grounded
        # answer, not a crash.
        return {
            "agent_messages": messages,
            "rag_answer": None,
            "pending_tool_calls": [],
            "pending_submission": None,
            "next_step": "end",
        }

    messages = [*messages, {"role": "assistant", "content": [_block_to_dict(b) for b in response.content]}]

    if response.stop_reason == "max_tokens":
        truncation_retries = state.get("truncation_retries", 0) + 1
        if truncation_retries > MAX_VERIFICATION_RETRIES:
            return {
                "agent_messages": messages,
                "rag_answer": None,
                "truncation_retries": truncation_retries,
                "next_step": "end",
            }
        messages = [
            *messages,
            {
                "role": "user",
                "content": "Your previous response was cut off before it finished. "
                "Please give a shorter, complete answer.",
            },
        ]
        return {
            "agent_messages": messages,
            "truncation_retries": truncation_retries,
            "pending_tool_calls": [],
            "pending_submission": None,
            "next_step": "agent",
        }

    tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
    if not tool_use_blocks:
        trace = state.get("tool_trace") or []
        no_tool_call_retries = state.get("no_tool_call_retries", 0)
        if not trace and no_tool_call_retries < MAX_VERIFICATION_RETRIES:
            no_tool_call_retries += 1
            messages = [
                *messages,
                {
                    "role": "user",
                    "content": "Before concluding you don't have enough information, "
                    "try retrieve_documents (and get_fee, if relevant) at least once.",
                },
            ]
            return {
                "agent_messages": messages,
                "no_tool_call_retries": no_tool_call_retries,
                "pending_tool_calls": [],
                "pending_submission": None,
                "next_step": "agent",
            }
        return {
            "agent_messages": messages,
            "rag_answer": None,
            "pending_tool_calls": [],
            "pending_submission": None,
            "next_step": "end",
        }

    # A submit_answer alongside other tool calls in the same turn is not
    # acted on this iteration — see module docstring.
    other_blocks = [b for b in tool_use_blocks if b.name != "submit_answer"]
    submit_block = None if other_blocks else next((b for b in tool_use_blocks if b.name == "submit_answer"), None)

    return {
        "agent_messages": messages,
        "pending_tool_calls": [{"id": b.id, "name": b.name, "input": b.input} for b in other_blocks],
        "pending_submission": {"id": submit_block.id, "input": submit_block.input} if submit_block is not None else None,
        "next_step": "tools" if other_blocks else "verify",
    }


@traced_node("tools")
def tools_node(state: GraphState, config: RunnableConfig) -> dict[str, Any]:
    """Executes every tool call the `agent` node's last turn requested."""
    db = _get_db(config)
    tool_iterations = state.get("tool_iterations", 0)
    trace = list(state.get("tool_trace") or [])
    chunk_lookup = dict(state.get("chunk_lookup") or {})
    fee_values = set(state.get("fee_values") or [])
    office_names = set(state.get("office_names") or [])
    requirement_labels = set(state.get("requirement_labels") or [])

    tool_results_content: list[dict[str, Any]] = []
    for call in state["pending_tool_calls"]:
        tool_iterations += 1
        if tool_iterations > MAX_TOOL_ITERATIONS:
            return {
                "rag_answer": None,
                "tool_iterations": tool_iterations,
                "pending_tool_calls": [],
                "next_step": "end",
            }
        with traced_tool(call["name"], call["input"]) as tool_span:
            result = call_tool(db, call["name"], call["input"])
            tool_span.update(output=result)
        trace.append({"tool": call["name"], "arguments": call["input"], "result": result})
        _collect_seen_values(call["name"], result, chunk_lookup, fee_values, office_names, requirement_labels)
        tool_results_content.append(
            {"type": "tool_result", "tool_use_id": call["id"], "content": json.dumps(result)}
        )

    messages = [*state["agent_messages"], {"role": "user", "content": tool_results_content}]

    return {
        "agent_messages": messages,
        "tool_trace": trace,
        "chunk_lookup": chunk_lookup,
        "fee_values": sorted(fee_values),
        "office_names": sorted(office_names),
        "requirement_labels": sorted(requirement_labels),
        "tool_iterations": tool_iterations,
        "pending_tool_calls": [],
        "next_step": "agent",
    }


@traced_node("verify")
def verify_node(state: GraphState, config: RunnableConfig) -> dict[str, Any]:
    """Checks a submitted answer against every value a tool call this
    turn actually returned — `app.chat.agent._verify_submission`,
    unchanged."""
    submission = state["pending_submission"]["input"]
    chunk_lookup = state.get("chunk_lookup") or {}
    fee_values = set(state.get("fee_values") or [])
    office_names = set(state.get("office_names") or [])
    requirement_labels = set(state.get("requirement_labels") or [])

    error = _verify_submission(submission, chunk_lookup, fee_values, office_names, requirement_labels)

    if error is None:
        chunk_citations = submission.get("chunk_citations") or []
        citations = _build_citations(chunk_citations, chunk_lookup)
        return {
            "rag_answer": {
                "text": submission["answer"],
                "citations": [
                    {
                        "source_document_id": str(c.source_document_id),
                        "source_url": c.source_url,
                        # `_build_citations` (app.chat.agent, unmodified)
                        # actually assigns `verified_at` from
                        # `retrieve_documents`'s chunk dict, which is
                        # already an ISO string — not the datetime its
                        # `Citation` dataclass type hint implies. Handle
                        # both rather than assume: a real datetime
                        # (e.g. from a future caller that fixes that
                        # quirk) still serializes correctly.
                        "verified_at": (
                            c.verified_at.isoformat()
                            if hasattr(c.verified_at, "isoformat")
                            else c.verified_at
                        ),
                    }
                    for c in citations
                ],
                "cited_chunk_ids": [c["chunk_id"] for c in chunk_citations if c["chunk_id"] in chunk_lookup],
                "trace": state.get("tool_trace") or [],
            },
            "verification_error": None,
            "pending_submission": None,
            "next_step": "end",
        }

    verification_retries = state.get("verification_retries", 0) + 1
    if verification_retries > MAX_VERIFICATION_RETRIES:
        return {
            "rag_answer": None,
            "verification_retries": verification_retries,
            "pending_submission": None,
            "next_step": "end",
        }

    messages = [
        *state["agent_messages"],
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": state["pending_submission"]["id"],
                    "content": error,
                    "is_error": True,
                }
            ],
        },
    ]
    return {
        "agent_messages": messages,
        "verification_retries": verification_retries,
        "pending_submission": None,
        "verification_error": error,
        "next_step": "agent",
    }
