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

Task Group 7 (Langfuse): every model call is wrapped as a generation
span, every tool call as a tool span, and — since this loop is exactly
where the tool-selection instability Task Group 3/4 measured actually
happens — every `None` return (a refused turn) records *why*
(`_refusal_reason`) on the top-level trace, not just that it happened.
A trace tree alone shows which tools were or weren't called; the reason
tag makes the five structurally distinct refusal causes (API failure,
truncated response, no tool call ever tried, tool-iteration limit,
failed verification) filterable without re-reading every trace by hand.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field

import anthropic
from sqlalchemy.orm import Session

from app.chat.tools import TOOL_SCHEMAS, call_tool
from app.engine.types import Citation
from app.observability.tracing import traced_generation, traced_tool, turn_trace

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

If a question names or implies the applicant's age — including asking \
specifically about a child's or minor's fee — pass that age to get_fee; \
some services have a separate, lower fee tier for applicants under 16, \
and get_fee only returns it when age is given.

When you have enough information to answer, call submit_answer with:
- answer: your plain-language answer text
- chunk_citations: every retrieved chunk your answer actually draws on \
(empty list only if retrieve_documents was never called, or its results \
contributed nothing to your answer at all) — this covers anything you \
learned from document text, including a fee, office, or step merely \
mentioned in a passage, and including a side note or caveat, not just \
the answer's main point. If you called retrieve_documents and your \
answer states ANY fact, number, or detail that came from those results \
— even in passing — you MUST list that chunk's id here. Leaving \
chunk_citations empty after calling retrieve_documents is only correct \
when you end up not using its results at all.
- fee_values_used: ONLY a fee amount you got from get_fee, resolve_case, \
or compare_amendment_vs_renewal. Do not put a fee amount here just \
because a retrieved passage mentions it (e.g. a fine or fee stated in \
cited document text) — that is already covered by chunk_citations. \
Leave this empty unless you actually called one of those three tools.
- office_names_used: ONLY an office name you got from find_office or \
resolve_case. Do not put an office name here just because a retrieved \
passage mentions it — that is already covered by chunk_citations. Leave \
this empty unless you actually called one of those two tools.
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
            "fee_values_used": {
                "type": "array",
                "items": {"type": "number"},
                "description": "Only fee amounts obtained from get_fee/resolve_case/"
                "compare_amendment_vs_renewal — not a fee amount merely mentioned in "
                "cited document text.",
            },
            "office_names_used": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Only office names obtained from find_office/resolve_case — "
                "not an office name merely mentioned in cited document text.",
            },
            "requirement_labels_used": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["answer", "chunk_citations", "fee_values_used", "office_names_used", "requirement_labels_used"],
    },
}

ALL_SCHEMAS = [*TOOL_SCHEMAS, SUBMIT_ANSWER_SCHEMA]

# Tools usable with no Case ID at all — retrieve_documents, get_fee,
# find_office never need one (see SYSTEM_PROMPT). Used to restrict the
# forced first-turn tool choice (see the "tool-selection instability"
# fix) when no case_id was given: without this restriction, a model
# forced to call *something* on turn 0 with no case in hand sometimes
# grabbed a case-scoped tool with a placeholder id instead of the
# obviously-relevant retrieve_documents/get_fee — observed directly,
# wasting an iteration on a call that could only ever fail.
_CASE_INDEPENDENT_TOOL_NAMES = {"retrieve_documents", "get_fee", "find_office"}
CASE_INDEPENDENT_SCHEMAS = [s for s in TOOL_SCHEMAS if s["name"] in _CASE_INDEPENDENT_TOOL_NAMES]


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


def _value_appears_in_cited_chunk_text(value: float, chunk_citations: list[dict], chunk_lookup: dict[str, dict]) -> bool:
    """A fee amount is also considered grounded when it appears, as
    text, within a chunk the submission actually cited — not just when
    it came from get_fee/resolve_case/compare_amendment_vs_renewal.
    Structural backstop for a real failure observed directly: a
    correctly-retrieved, correctly-cited chunk's own text stated a fine
    amount (e.g. "a fine of Rs. 20,000"), the model reported it in
    fee_values_used per the system prompt's instruction at the time, and
    verification rejected an answer that was, in fact, fully grounded —
    the chunk_citations check alone already proves it, this only widens
    what counts as proof for a number specifically. Requires the chunk
    to be a genuine citation (checked separately, above) and the value
    to actually appear in that chunk's own text — never trusts an
    uncited chunk or a value absent from the cited text."""
    variants = {f"{value:,.2f}", f"{value:.2f}", f"{int(value):,}", str(int(value))}
    for citation in chunk_citations:
        chunk = chunk_lookup.get(citation.get("chunk_id"))
        if chunk is None:
            continue
        text = chunk.get("text", "")
        if any(variant in text for variant in variants):
            return True
    return False


# Observed directly, reproducibly, across independent runs (see
# design.md's citation-malformation fix): on a long/structured answer,
# the model sometimes doesn't populate the real `chunk_citations` array
# parameter at all, and instead appends what looks like hand-typed tool-
# call XML — `</answer>` followed by either `<chunk_citations>[...]` or
# `<parameter name="chunk_citations">[...]` — as trailing TEXT inside the
# free-text `answer` string field itself. The citation *content* in that
# trailing block is typically correct (real chunk ids, real quoted
# spans); only its placement is wrong. Anchored to the end of the string
# (`\s*$`) since every observed instance is trailing content, not
# mid-answer text — this must never match a legitimate citation-shaped
# sentence appearing naturally within the prose.
_MALFORMED_CITATION_TAG = re.compile(
    r'(?:</answer>\s*)?<(?:chunk_citations|parameter\s+name=["\']chunk_citations["\'])>'
    r'\s*(\[.*\])\s*(?:</(?:chunk_citations|parameter)>)?\s*$',
    re.DOTALL,
)

# The exact wording of the generic "cited none" rejection — compared
# against in `_run_loop` to decide whether the more specific, malformed-
# citation-aware retry message (`_describe_citation_mistake`) applies,
# without coupling that decision to `_verify_submission`'s internals.
_CITED_NONE_ERROR = (
    "You retrieved document chunks but cited none — cite every chunk "
    "your answer actually draws on."
)


def _salvage_malformed_citations(submission: dict, chunk_lookup: dict[str, dict]) -> dict | None:
    """Recovers a submission that hit the malformed-citation-placement
    mistake described above, returning a corrected copy (citations moved
    into `chunk_citations`, the pseudo-XML stripped from `answer`) — or
    None if there is nothing to salvage or the extracted data can't be
    trusted.

    Safety: only ever salvages when the JSON block parses cleanly, every
    extracted entry has both a `chunk_id` and `quoted_span`, AND every
    extracted chunk_id is a genuine member of `chunk_lookup` — i.e.
    something `retrieve_documents` actually returned this turn. A single
    unrecognized id abandons the salvage entirely rather than trusting
    part of it; the turn falls through to normal verification (and the
    specific retry message below) exactly as it would without this
    function. This never manufactures a citation retrieval didn't
    actually produce — it only recovers one that did happen, misplaced
    in transport.
    """
    if submission.get("chunk_citations"):
        return None  # already has real, structured citations — nothing to salvage
    answer_text = submission.get("answer") or ""
    match = _MALFORMED_CITATION_TAG.search(answer_text)
    if match is None:
        return None
    try:
        parsed = json.loads(match.group(1))
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(parsed, list) or not parsed:
        return None
    for entry in parsed:
        if not isinstance(entry, dict) or "chunk_id" not in entry or "quoted_span" not in entry:
            return None
        if entry["chunk_id"] not in chunk_lookup:
            return None

    cleaned_answer = answer_text[: match.start()].rstrip()
    if not cleaned_answer:
        return None
    salvaged = dict(submission)
    salvaged["answer"] = cleaned_answer
    salvaged["chunk_citations"] = parsed
    return salvaged


def _describe_citation_mistake(answer_text: str) -> str | None:
    """Builds a retry message naming the actual mistake — citation JSON
    embedded as text inside `answer` — and quoting the malformed
    fragment, for the case `_salvage_malformed_citations` couldn't
    recover (an unrecognized chunk_id, unparseable JSON, etc.). The
    generic "cited none" message doesn't tell the model *why* its
    citations weren't seen; observed directly, the retry reproduced the
    identical malformed pattern verbatim when given only that generic
    message — this names the mistake so the retry has a real chance of
    fixing it instead of repeating it. Returns None when the answer text
    doesn't match the known malformed pattern at all (a genuine "forgot
    to cite" case), so the generic message still applies there.
    """
    match = _MALFORMED_CITATION_TAG.search(answer_text or "")
    if match is None:
        return None
    fragment = answer_text[match.start() : match.end()]
    return (
        "Your previous attempt did not actually leave citations out — it placed "
        "the citation data as literal text inside the `answer` field instead of "
        "using the `chunk_citations` array parameter. The malformed text you "
        f"produced was:\n\n{fragment}\n\n"
        "Do not write citation JSON or XML-like tags inside `answer` — keep "
        "`answer` as plain prose only. Put each cited chunk's id and "
        "quoted_span as an object in the `chunk_citations` array parameter."
    )


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
        return _CITED_NONE_ERROR

    for value in submission.get("fee_values_used") or []:
        if any(abs(float(value) - seen) < 0.01 for seen in fee_values):
            continue
        if _value_appears_in_cited_chunk_text(float(value), chunk_citations, chunk_lookup):
            continue
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
    with turn_trace(case_id, query) as turn_span:
        result, reason = _run_loop(db, query, case_id)
        if result is None:
            turn_span.update(output={"refused": True, "refusal_reason": reason})
        else:
            turn_span.update(
                output={
                    "refused": False,
                    "answer": result.text,
                    "tool_calls": [r.tool for r in result.trace],
                }
            )
        return result


def _run_loop(db: Session, query: str, case_id: str | None) -> tuple[AgentAnswer | None, str | None]:
    """The tool-use loop itself, factored out of `answer_with_agent` so
    every exit point can be tagged with a short, distinct
    `refusal_reason` string — that tag, not just the trace tree, is what
    lets a Langfuse view group refused turns by cause rather than
    requiring every trace to be read by hand."""
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
            if len(messages) == 1:
                # First turn: force a real tool call — `tools` excludes
                # submit_answer and `tool_choice` requires one of them,
                # so the model cannot decline (plain text) or submit a
                # final answer without having tried anything first. This
                # replaces relying on the model to *choose* to look
                # (the original design) with making "looked at least
                # once" structurally unavoidable — see design.md's
                # "tool-selection instability" fix: observed directly
                # that the same query sometimes answered correctly
                # (retrieved, cited, grounded) and sometimes refused
                # outright with no tool call at all, run to run. When no
                # case_id is available, only the case-independent tools
                # are offered — forcing a choice among all six otherwise
                # let the model grab a case-scoped tool with a
                # placeholder id, wasting an iteration on a call that
                # could only ever fail (also observed directly).
                first_turn_schemas = TOOL_SCHEMAS if case_id else CASE_INDEPENDENT_SCHEMAS
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
            # An API failure during tool selection — same explicit
            # no-relevant-match response as any other failure to
            # produce a tool-grounded answer, not a crash.
            return None, "api_failure"
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "max_tokens":
            # The response (possibly including an in-progress tool_use
            # block's arguments) was cut off mid-generation — never trust
            # a truncated submit_answer's fields.
            truncation_retries += 1
            if truncation_retries > MAX_VERIFICATION_RETRIES:
                return None, "truncation_exhausted"
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
            # No tool call at all. This branch is now structurally
            # unreachable on the first turn — `tool_choice={"type":
            # "any"}` there forces a real tool call, so the model cannot
            # decline without having looked (see the forced-first-call
            # block above; this superseded the original design, where
            # the model merely being *nudged* to try a tool proved
            # unreliable — observed directly: the same query sometimes
            # answered correctly after retrieving, and sometimes refused
            # outright with zero tool calls, run to run). Kept as a
            # defensive fallback for a later turn (after at least one
            # tool has already been tried) rather than removed, in case
            # the model produces plain text again after seeing results —
            # that case still gets one nudge before giving up.
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
            return None, "no_tool_call_exhausted"

        submit_block = next((b for b in tool_use_blocks if b.name == "submit_answer"), None)
        tool_results_content: list[dict] = []

        for block in tool_use_blocks:
            if block.name == "submit_answer":
                continue
            tool_iterations += 1
            if tool_iterations > MAX_TOOL_ITERATIONS:
                return None, "tool_iteration_limit"
            with traced_tool(block.name, block.input) as tool_span:
                result = call_tool(db, block.name, block.input)
                tool_span.update(output=result)
            trace.append(ToolCallRecord(tool=block.name, arguments=block.input, result=result))
            _collect_seen_values(
                block.name, result, chunk_lookup, fee_values, office_names, requirement_labels
            )
            tool_results_content.append(
                {"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(result)}
            )

        if submit_block is not None:
            # Salvage before verifying: a submission that looks like it
            # left chunk_citations empty sometimes actually placed real
            # citation data as malformed text inside `answer` instead
            # (see `_salvage_malformed_citations`) — recover that first,
            # so verification below runs against the corrected
            # citations/answer exactly as it would if the model had
            # populated the field correctly in the first place.
            submission = _salvage_malformed_citations(submit_block.input, chunk_lookup)
            if submission is None:
                submission = submit_block.input

            error = _verify_submission(
                submission, chunk_lookup, fee_values, office_names, requirement_labels
            )
            if error is None:
                chunk_citations = submission.get("chunk_citations") or []
                return (
                    AgentAnswer(
                        text=submission["answer"],
                        citations=_build_citations(chunk_citations, chunk_lookup),
                        cited_chunk_ids=[
                            c["chunk_id"] for c in chunk_citations if c["chunk_id"] in chunk_lookup
                        ],
                        trace=trace,
                    ),
                    None,
                )
            verification_retries += 1
            if verification_retries > MAX_VERIFICATION_RETRIES:
                return None, "verification_exhausted"
            if error == _CITED_NONE_ERROR:
                # Salvage couldn't recover this one (bad JSON, an
                # unrecognized chunk_id, etc.) — if it's still the known
                # malformed-citation pattern, tell the model exactly what
                # it did wrong instead of the generic message, which the
                # retry has already been observed to reproduce verbatim.
                specific = _describe_citation_mistake(submission.get("answer", ""))
                if specific is not None:
                    error = specific
            tool_results_content.append(
                {"type": "tool_result", "tool_use_id": submit_block.id, "content": error, "is_error": True}
            )

        if not tool_results_content:
            return None, "no_progress"
        messages.append({"role": "user", "content": tool_results_content})
