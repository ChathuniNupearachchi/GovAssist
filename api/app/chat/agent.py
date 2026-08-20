"""6.11.1 Agentic tool-use loop — the open-question answering path.

Replaces Phase 5/6.7's single-shot retrieve-then-generate call with a
bounded `claude-sonnet-5` tool-use loop over the six system-capability
tools in `app.chat.tools`. The model selects which tool(s) to call;
`app.chat.tools.call_tool` computes the actual answer. The model never
produces a fee, office, timeline, or requirement value itself — it
finishes by calling a seventh, synthetic `submit_answer` tool whose
arguments (the answer text, plus which chunk ids / fee amounts / office
names / requirement labels it drew on) are checked against what the
real tool calls this turn actually returned before the answer is
trusted. This is the same verify → retry-once → fall back to the
explicit "no relevant match" response shape 6.9 already established for
single-shot generation — see rag-answering spec's "every generated
response, including a tool-composed one" (6.11's broadening of 6.9).

If the model's response ever contains no tool call at all (it neither
requests a system-capability tool nor calls `submit_answer`), that is
treated as an implicit "I don't know" — the same explicit no-relevant-
match response weak retrieval itself produces, not a bare, ungrounded
chat reply.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field

import anthropic
from sqlalchemy.orm import Session

from app.chat.tools import TOOL_SCHEMAS, call_tool
from app.engine.types import Citation

MODEL = "claude-sonnet-5"
MAX_TOOL_ITERATIONS = 6
MAX_VERIFICATION_RETRIES = 1
# Higher than a single generation call needs (Phase 5 used 1024) —
# this model's responses include thinking-block tokens (observed
# directly: a 1024 cap truncated a multi-step turn's final submit_answer
# call mid-arguments, before it recorded any of the tool-composed
# answer's citations, leaving stop_reason "max_tokens"). Each call in
# the loop gets its own budget, so this is per-call, not cumulative.
MAX_TOKENS = 4096

SYSTEM_PROMPT = """You help a Sri Lankan citizen with questions about \
Department of Immigration and Emigration passport rules and their own \
case, using ONLY the tools available to you. Never state a fee amount, \
an office name, a processing timeline, or a document/step/prerequisite \
requirement unless a tool call you made this turn actually returned it \
— you may compose and explain, but you never compute or recall such a \
value yourself.

A question comparing two paths (for example, "should I amend my \
passport or get a new one?") needs the fee and requirements for BOTH \
paths — call the tools for both before answering, and use \
compare_amendment_vs_renewal or two separate get_fee calls plus a \
retrieve_documents call to ground any timeline or process details.

retrieve_documents and get_fee never need a case — call them for any \
question, with or without a Case ID. get_next_question, resolve_case, \
and compare_amendment_vs_renewal need a Case ID: if the message you \
receive starts with "Case ID: ...", use that id with those tools \
directly, without asking the citizen for it. If no Case ID is given and \
a question would otherwise need one, prefer answering with get_fee \
(called for each relevant service) and retrieve_documents instead of \
asking — most comparison questions can be answered generally that way.

When you have enough information to answer, call submit_answer with:
- answer: your plain-language answer text
- chunk_citations: every retrieved chunk your answer actually draws on \
(empty list if you used none) — this covers anything you learned from \
document text, including a document or step merely mentioned in a \
passage
- fee_values_used: every fee amount (as numbers) your answer states
- office_names_used: every office name your answer states
- requirement_labels_used: ONLY a requirement label exactly as returned \
by resolve_case or compare_amendment_vs_renewal, when you assert it is \
officially part of THIS CITIZEN'S case checklist. Do not put a document \
or step here just because a retrieved passage mentions it in passing —
that is already covered by chunk_citations. Leave this empty unless you \
actually called resolve_case or compare_amendment_vs_renewal.

If no tool gives you enough to answer the question, do NOT call \
submit_answer — just say in plain text that you don't have that \
information. Never guess."""

SUBMIT_ANSWER_SCHEMA = {
    "name": "submit_answer",
    "description": (
        "Give your final answer to the citizen. Call this only once you have "
        "everything you need from the other tools."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "answer": {"type": "string"},
            "chunk_citations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "chunk_id": {"type": "string"},
                        "quoted_span": {"type": "string"},
                    },
                    "required": ["chunk_id", "quoted_span"],
                },
            },
            "fee_values_used": {"type": "array", "items": {"type": "number"}},
            "office_names_used": {"type": "array", "items": {"type": "string"}},
            "requirement_labels_used": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["answer", "chunk_citations", "fee_values_used", "office_names_used", "requirement_labels_used"],
    },
}

ALL_SCHEMAS = [*TOOL_SCHEMAS, SUBMIT_ANSWER_SCHEMA]


@dataclass(frozen=True)
class ToolCallRecord:
    tool: str
    arguments: dict
    result: dict


@dataclass(frozen=True)
class AgentAnswer:
    text: str
    citations: list[Citation]
    cited_chunk_ids: list[str]
    trace: list[ToolCallRecord] = field(default_factory=list)


def _collect_seen_values(
    tool_name: str,
    result: dict,
    chunk_lookup: dict[str, dict],
    fee_values: set[float],
    office_names: set[str],
    requirement_labels: set[str],
) -> None:
    """Records every chunk/fee/office/requirement value a real tool call
    actually returned this turn — the set every `submit_answer` value is
    checked against."""
    if "error" in result:
        return

    if tool_name == "retrieve_documents":
        for chunk in result.get("chunks", []):
            chunk_lookup[chunk["chunk_id"]] = chunk

    fee_dicts = []
    if tool_name == "get_fee" and result.get("found"):
        fee_dicts.append(result["fee"])
    elif tool_name == "compare_amendment_vs_renewal":
        for side in ("renewal", "amendment"):
            side_result = result.get(side) or {}
            if side_result.get("fee"):
                fee_dicts.append(side_result["fee"])
            for r in side_result.get("requirements", []):
                requirement_labels.add(r["label"])
    elif tool_name == "resolve_case" and result.get("ready"):
        if result.get("fee"):
            fee_dicts.append(result["fee"])
        for o in result.get("offices", []):
            office_names.add(o["name"])
        for r in result.get("requirements", []):
            requirement_labels.add(r["label"])

    for fee in fee_dicts:
        fee_values.add(float(fee["base_amount"]))

    if tool_name == "find_office":
        for o in result.get("offices", []):
            office_names.add(o["name"])


def _verify_submission(
    submission: dict,
    chunk_lookup: dict[str, dict],
    fee_values: set[float],
    office_names: set[str],
    requirement_labels: set[str],
) -> str | None:
    """Returns None if the submission is fully grounded in this turn's
    tool results, or an explanation string for the model if not."""
    chunk_citations = submission.get("chunk_citations") or []
    for citation in chunk_citations:
        if citation.get("chunk_id") not in chunk_lookup:
            return (
                f"chunk_citations includes chunk_id '{citation.get('chunk_id')}', "
                "which was not returned by any retrieve_documents call this turn."
            )
    if chunk_lookup and not chunk_citations:
        return (
            "You retrieved document chunks but cited none — cite every chunk "
            "your answer actually draws on."
        )

    for value in submission.get("fee_values_used") or []:
        if not any(abs(float(value) - seen) < 0.01 for seen in fee_values):
            return f"fee_values_used includes {value}, which no tool call this turn returned."

    for name in submission.get("office_names_used") or []:
        if name not in office_names:
            return f"office_names_used includes '{name}', which no tool call this turn returned."

    for label in submission.get("requirement_labels_used") or []:
        if label not in requirement_labels:
            return f"requirement_labels_used includes '{label}', which no tool call this turn returned."

    return None


def _build_citations(chunk_citations: list[dict], chunk_lookup: dict[str, dict]) -> list[Citation]:
    citations = []
    seen_documents: set[str] = set()
    for entry in chunk_citations:
        chunk = chunk_lookup.get(entry.get("chunk_id"))
        if chunk is None:
            continue
        if chunk["source_document_id"] in seen_documents:
            continue
        seen_documents.add(chunk["source_document_id"])
        citations.append(
            Citation(
                source_document_id=uuid.UUID(chunk["source_document_id"]),
                source_url=chunk["source_url"],
                verified_at=chunk["verified_at"],
            )
        )
    return citations


def _build_initial_message(query: str, case_id: str | None) -> str:
    if case_id is None:
        return query
    return f"Case ID: {case_id}\n\nQuestion: {query}"


def answer_with_agent(db: Session, query: str, case_id: str | None = None) -> AgentAnswer | None:
    """Run the tool-use loop for one open question. `case_id`, when the
    question was asked mid-case (the common path via `app.chat.router`),
    lets the model use the case-scoped tools (`get_next_question`,
    `resolve_case`, `compare_amendment_vs_renewal`) without having to
    ask the citizen for it — `get_fee`/`retrieve_documents` need no case
    at all and work either way. Returns None when no tool-grounded
    answer could be produced — the caller falls back to the explicit
    no-relevant-match response, same as a weak retrieval match."""
    client = anthropic.Anthropic()
    messages: list[dict] = [{"role": "user", "content": _build_initial_message(query, case_id)}]
    trace: list[ToolCallRecord] = []
    chunk_lookup: dict[str, dict] = {}
    fee_values: set[float] = set()
    office_names: set[str] = set()
    requirement_labels: set[str] = set()

    tool_iterations = 0
    # Three independent one-retry budgets, kept separate rather than one
    # shared counter — a truncated response and a fabricated citation
    # are different failure modes, and the request's own DONE WHEN
    # criteria expect a retry chance for rephrasing/tool-selection
    # failures specifically, not a budget that could be exhausted by an
    # unrelated hiccup earlier in the same turn.
    verification_retries = 0
    truncation_retries = 0
    no_tool_call_retries = 0

    while True:
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=SYSTEM_PROMPT,
                tools=ALL_SCHEMAS,
                messages=messages,
            )
        except Exception:
            # An API failure during tool selection — same explicit
            # no-relevant-match response as any other failure to
            # produce a tool-grounded answer, not a crash.
            return None
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "max_tokens":
            # The response (possibly including an in-progress tool_use
            # block's arguments) was cut off mid-generation — never trust
            # a truncated submit_answer's fields.
            truncation_retries += 1
            if truncation_retries > MAX_VERIFICATION_RETRIES:
                return None
            messages.append(
                {
                    "role": "user",
                    "content": "Your previous response was cut off before it finished. "
                    "Please give a shorter, complete answer.",
                }
            )
            continue

        tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
        if not tool_use_blocks:
            # No tool call at all. If nothing has been tried yet this
            # turn, give one nudge to actually check before giving up —
            # observed directly: the model sometimes answers "I don't
            # know" in prose without calling retrieve_documents first,
            # even though a wider retrieval would have found something
            # (the same content this project's own weak-match retry
            # exists to give a second chance to). Once at least one tool
            # has actually been tried, a further no-tool-call response is
            # the real "I don't know" — see module docstring.
            if not trace and no_tool_call_retries < MAX_VERIFICATION_RETRIES:
                no_tool_call_retries += 1
                messages.append(
                    {
                        "role": "user",
                        "content": "Before concluding you don't have enough information, "
                        "try retrieve_documents (and get_fee, if relevant) at least once.",
                    }
                )
                continue
            return None

        submit_block = next((b for b in tool_use_blocks if b.name == "submit_answer"), None)
        tool_results_content: list[dict] = []

        for block in tool_use_blocks:
            if block.name == "submit_answer":
                continue
            tool_iterations += 1
            if tool_iterations > MAX_TOOL_ITERATIONS:
                return None
            result = call_tool(db, block.name, block.input)
            trace.append(ToolCallRecord(tool=block.name, arguments=block.input, result=result))
            _collect_seen_values(
                block.name, result, chunk_lookup, fee_values, office_names, requirement_labels
            )
            tool_results_content.append(
                {"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(result)}
            )

        if submit_block is not None:
            error = _verify_submission(
                submit_block.input, chunk_lookup, fee_values, office_names, requirement_labels
            )
            if error is None:
                chunk_citations = submit_block.input.get("chunk_citations") or []
                return AgentAnswer(
                    text=submit_block.input["answer"],
                    citations=_build_citations(chunk_citations, chunk_lookup),
                    cited_chunk_ids=[c["chunk_id"] for c in chunk_citations if c["chunk_id"] in chunk_lookup],
                    trace=trace,
                )
            verification_retries += 1
            if verification_retries > MAX_VERIFICATION_RETRIES:
                return None
            tool_results_content.append(
                {"type": "tool_result", "tool_use_id": submit_block.id, "content": error, "is_error": True}
            )

        if not tool_results_content:
            return None
        messages.append({"role": "user", "content": tool_results_content})
