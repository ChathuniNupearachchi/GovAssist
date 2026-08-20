## Context

Phase 6's open-question path (`app/rag/answer.py::answer_question`) is
single-shot: retrieve, then one grounded-generation call, citation-
verified (6.9) against exactly the chunks that one retrieval returned.
It has no way to make a second retrieval, and no way to touch the rules
engine at all — a fee, an office, and a requirement set are each a
different Python function (`app.engine.fees.resolve_fee`,
`app.engine.offices.resolve_offices`, `app.engine.requirements.
resolve_requirements`) that only `app/api/cases.py`'s routes call
directly. `app/engine/resolver.py::resolve_case` already computes an
`amendment_alternative` (a full fee + requirement set for the amendment
service) whenever `name_changed == "true"` is among the answers passed
in — this is the existing basis for 6.11.1's
`compare_amendment_vs_renewal` tool, not a new engine computation.

The intake path (`app/chat/router.py::handle_message`) already computes
everything 6.11.2/6.11.3 need to *present* — `next_question` returns the
canonical `Question`, and `extracted` is the exact dict of
attribute→value pairs about to be recorded — it just never turns either
into conversational text today.

`app/chat/classifier.py` is this codebase's existing structured-output
pattern (`client.messages.parse(..., output_format=PydanticModel)`,
confidence threshold, fallback on low confidence) — 6.11.2's rephrasing
follows the same shape. `app/rag/generation.py`'s 6.9 verification gate
(verify → retry once → fall back) is the existing pattern 6.11.1's tool-
composed-answer verification reuses, not a new mechanism.

**Sequencing dependency, stated plainly:** this proposal's `rag-
answering` and `case-resolution-data-model` deltas are written as
`MODIFIED` requirements against the text those capabilities will carry
once `phase-6-6-to-6-10-rag-quality-and-sessions` is archived (6.9's
citation-verification requirement, 6.10's `CHAT_MESSAGE` requirement) —
not against what's in `openspec/specs/` today, since that change hasn't
been archived yet at proposal time. **Archive `phase-6-6-to-6-10-rag-
quality-and-sessions` before applying this change**, or `openspec
archive`'s diff against main specs will not line up. This is a planning-
time fact, not a design decision, but it belongs here because it affects
apply order, not just spec bookkeeping.

## Goals / Non-Goals

**Goals:**
- Let an open question that needs more than one system capability (a
  fee lookup, a document lookup, a comparison) be answered by chaining
  read-only tool calls, with every plan-shaped value traceable to a
  specific tool result.
- Make the intake conversation read as a conversation — rephrased
  questions, visible acknowledgement of recorded facts — without moving
  question selection or plan/fee/office computation off the
  deterministic engine.
- Every new LLM call degrades to today's behavior on failure: rephrasing
  fails → canonical prompt; acknowledgement fails → no acknowledgement,
  question still asked; tool-selection fails → the existing "no relevant
  match" response, not a crash.

**Non-Goals:**
- No change to `next_question.py`'s selection logic, to any
  `app/engine/` function's own behavior, or to what's allowed to produce
  a plan, fee, office, or checklist — tools call existing engine
  functions read-only; nothing here adds a new place fee/office logic
  lives.
- No new RAG ranking or chunking behavior — `retrieve_documents` wraps
  Phase 5/6.7's existing `retrieve()` unchanged; it becomes reachable as
  a tool, it isn't reimplemented.
- No conversation memory beyond what Phase 6.10 already persists — the
  agent's tool loop and the rephrasing/acknowledgement calls read the
  same `CASE_ANSWER` / recent-message state that already exists; this
  phase adds a `tool_trace` column, not a new memory mechanism.

## Decisions

### The agent loop: a bounded tool-use loop over `claude-sonnet-5`, not a framework
`client.messages.create(model=..., tools=[...], messages=[...])` is
called with all six tool schemas on every turn that routes to the
open-question path. While `stop_reason == "tool_use"`, each requested
tool block is executed against the real handler, its result appended to
the message list as a `tool_result` block, and the model is called
again — up to a fixed cap (6 iterations) before falling back to the
explicit no-relevant-match response, so a model stuck in a call loop
can't hang a citizen's turn indefinitely. This is a plain loop over the
existing Anthropic SDK, not LangGraph or any agent framework — consistent
with the project's already-recorded rejection of LangGraph (see the
phase-6-6-to-6-10 change's design.md): that rejection was about handing
*question selection* to an LLM agent, which this still doesn't do
(`next_question.py` is untouched); a bounded tool loop over one
provider's SDK for *answering an open question* is a much narrower
scope and doesn't create a second source of truth for anything the
engine already owns.

**Alternative considered:** `client.messages.tool_runner` (the SDK's
own agentic-loop helper, per the claude-api reference). Rejected for
this phase specifically because the per-turn tool-call trace (6.11.1's
own requirement) needs to observe every intermediate call and result,
and a hand-rolled loop makes that observation point explicit and
un-magic rather than reaching into a helper's internals to extract it.
Revisit if the hand-rolled loop grows unwieldy.

### Six tools, each a thin wrapper — no new business logic
Every tool handler is a direct call into an existing function, reshaped
to JSON:

| Tool | Wraps | Notes |
|---|---|---|
| `retrieve_documents(query)` | `app.rag.retrieval.retrieve` | Returns chunk id, text, source URL, verified-at per result — the same shape citation verification already checks against. |
| `get_fee(service, urgency)` | `app.engine.fees.resolve_fee` | `service` is `"renewal"` \| `"amendment"`, mapped to the two seeded rule versions the same way `resolver.py`'s `_approved_rule_version` already does. |
| `find_office(district, urgent)` | `app.engine.offices.resolve_offices` | Direct pass-through; `urgent` maps to `basis="urgent"/"normal"`. |
| `get_next_question(case_id)` | `app.engine.next_question.next_question` | Read-only; does not itself record anything. |
| `resolve_case(case_id)` | `app.engine.resolver.resolve_case` | If intake isn't complete, returns a structured "not ready, still need: {prompt}" result (same check `app/api/cases.py`'s route already makes) instead of raising — the model can react to that in prose rather than the turn erroring. |
| `compare_amendment_vs_renewal(case_id)` | `resolve_fee` (both services) + `resolve_requirements` (both services) | Unlike `resolve_case`'s conditional `amendment_alternative` (only populated when `name_changed=="true"`), this tool always computes both paths — the citizen asking "should I amend or renew" is, by definition, still deciding, so gating the amendment side on an answer they haven't necessarily given yet would defeat the tool's purpose. |

None of these functions change. `app/chat/tools.py` only defines JSON
schemas and calls them; `app/chat/agent.py` owns the loop.

### Verification scope: chunk citations from `retrieve_documents`, not every tool result
6.9's citation-verification gate already exists for chunk citations; it
extends to a tool-composed answer by checking the model's final
citations against the union of chunk ids returned by every
`retrieve_documents` call made during the turn (not just the last one,
since a multi-step turn may call it more than once). Fee, office, and
requirement values aren't "cited" the way a document passage is — they
are checked structurally instead, by the "traces to a tool result"
requirement: the composed answer's fee/office/requirement values are
matched against the set of values actually returned by `get_fee`/
`find_office`/`resolve_case`/`compare_amendment_vs_renewal` calls that
turn. Both checks use the same verify → retry-once → fall back to
no-relevant-match shape.

### Contextual rephrasing: same shape as `classifier.py`, one new safeguard
`app/chat/rephrase.py::rephrase_question(canonical_prompt, attribute,
recent_turns)` calls `claude-haiku-4-5` via `client.messages.parse` with
a Pydantic `output_format` returning `{rephrased_text: str,
target_attribute: str}`. The caller compares `target_attribute` against
the actual attribute `next_question.py` selected; a mismatch, a raised
exception, or a timeout all resolve to the same outcome — return the
canonical prompt unchanged. Because rephrasing runs *after*
`next_question.py` has already chosen the attribute, there is no path
by which rephrasing can influence which question gets asked — the
model only ever sees an attribute already decided, and can only affect
its own output text.

### Acknowledgement: engine-computed diff, not model-asserted content
`app/chat/acknowledge.py::build_acknowledgement(recorded_facts,
requirements_before, requirements_after)` is not an LLM call for its
factual content — `requirements_before`/`requirements_after` come from
two real `resolve_requirements` calls (with and without the newly
recorded answer(s) merged in), and the newly-triggered set is their
plain set difference. An LLM call (`claude-haiku-4-5`, same critical-
path budget as rephrasing) turns that verified `(fact, value,
[triggered requirement labels])` tuple into a natural sentence — a
wording task, not a fact-sourcing one. This mirrors 6.11.1's "tools
compute, the model composes" split at intake-acknowledgement scale: the
model is given already-true facts and asked only to phrase them,
identically to how `generation.py` is given already-retrieved chunks
and asked only to answer from them.

**Alternative considered:** ask the model to name which requirement
changed based on the extracted fact, without an engine diff. Rejected —
this is exactly the "never an inference" safeguard the request itself
calls for; the model has no way to know a requirement's gating
conditions without querying them, and asserting one it merely infers
from the fact's plausibility text is indistinguishable, from a citizen's
perspective, from an unverified generation the rest of this codebase
exists to prevent.

### `tool_trace` storage: a JSONB column on `CHAT_MESSAGE`, mirroring `cited_chunk_ids`
6.10 already added `cited_chunk_ids` (nullable JSONB) to `CHAT_MESSAGE`
for exactly this kind of "what actually computed this answer" audit
data. `tool_trace` follows the identical shape and precedent rather than
inventing a separate log store — "retrievable" (the request's own
DONE WHEN wording) is satisfied by it living in Postgres next to the
message it belongs to, queryable the same way. No new table, no new
capability for storage — see the `case-resolution-data-model` delta.

## Risks / Trade-offs

- **[Risk]** A six-tool schema plus a multi-step loop meaningfully
  increases `claude-sonnet-5` token usage and latency per open question,
  versus Phase 6's single retrieve-then-generate call. → **Mitigation:**
  accepted — multi-step chaining is this phase's explicit point, per the
  request ("that comparison exists in no single document"); the 6-
  iteration cap bounds the worst case.
- **[Risk]** `resolve_case` and `compare_amendment_vs_renewal` read
  `CASE_ANSWER`, so a tool-composed answer about "this case" is
  correct only as of the answers recorded so far — an incomplete case
  compared before intake finishes could read as more final than it is.
  → **Mitigation:** `resolve_case`'s "not ready" structured result (see
  above) and `compare_amendment_vs_renewal`'s "both paths always
  computed against current answers" framing keep the model able to say
  "based on what you've told me so far" rather than presenting a
  partial case as the final plan; final plans still only ever come from
  `POST /case/{id}/resolve`, not from a chat turn.
- **[Risk]** Verifying fee/office/requirement values structurally (not
  via a citation id, since they aren't chunks) is a looser check than
  6.9's exact chunk-id membership test — a paraphrased number could in
  principle slip past a naive string-equality check (e.g. "LKR
  10,000.00" vs "LKR 10,000"). → **Mitigation:** compare parsed numeric/
  identifier values, not raw text, the same way `resolve_case`'s API
  response already serializes `base_amount` as a float rather than a
  formatted string — this is a task-level implementation detail, not a
  design gap, but recorded here so it isn't lost between design and
  tasks.
- **[Trade-off]** Two more critical-path LLM calls per intake turn
  (rephrasing, acknowledgement) beyond the existing classifier call.
  → Accepted per the request's own explicit choice of `claude-haiku-
  4-5` for both — "light work, on the critical path" — and both fail
  open to today's behavior, so a slow or failed call degrades UX, not
  correctness.

## Migration Plan

1. Alembic migration: add `CHAT_MESSAGE.tool_trace` (JSONB, nullable) —
   additive, same shape as 6.10's `cited_chunk_ids` migration. Rollback
   drops the column.
2. `app/chat/tools.py` + `app/chat/agent.py` land together — the agent
   loop has no caller yet at this point, so this step ships dead code
   safely testable in isolation.
3. `app/rag/answer.py` (or its caller in `app/chat/router.py`) is
   rewired to call the new agent instead of `answer_question`'s old
   single-shot path — this is the cutover point; the old
   `retrieve()`/`generate_answer()` functions are unchanged and become
   `retrieve_documents`'s and (indirectly) the agent's implementation,
   not removed.
4. `app/chat/rephrase.py` and `app/chat/acknowledge.py` land, then
   `app/chat/router.py::handle_message` wires both in around the
   existing record/answer flow.
5. Full 89-test regression run before and after each step; this
   change's own new tests (multi-step trace, no-fabricated-value
   assertion, rephrasing fallback x2, acknowledgement content, malformed
   tool arguments) added alongside.

## Open Questions

None remaining that would change the approach. The one sequencing fact
this design depends on — archiving `phase-6-6-to-6-10-rag-quality-and-
sessions` before this change is applied — is stated as a hard
precondition above, not left open.
