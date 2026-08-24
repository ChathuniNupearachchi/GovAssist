## Why

Phase 6's chat surface can only do two things: record a fact, or answer
one retrieved-and-generated question. It cannot compose an answer that
draws on more than one system capability in a single turn — "should I
amend my passport or get a new one?" needs two fee lookups and a
document lookup, and nothing today can chain them. Separately, the
intake reads as a form, not a conversation: every question is the exact
canonical prompt regardless of what the citizen just said, and an
extracted fact is recorded silently, so a citizen who says "I got
married" sees no acknowledgment that anything happened before the next
unrelated-sounding question arrives. This phase gives the open-question
path the ability to chain system capabilities together, and gives the
intake path a conversational surface — without moving plan, fee, office,
or requirement production out of the rules engine, which stays their
only source.

## What Changes

- **6.11.1 Agentic tool calling**: the open-question answering path
  (previously single-shot retrieve-then-generate) becomes a
  `claude-sonnet-5` tool-use loop over six tools —
  `retrieve_documents`, `get_fee`, `find_office`, `get_next_question`,
  `resolve_case`, `compare_amendment_vs_renewal` — each a thin wrapper
  over an existing engine or RAG function. Every fee, office, timeline,
  or requirement value a response contains SHALL have come from a tool
  result; Claude selects tools and composes the surrounding prose, never
  the numbers. Multi-step chaining (e.g. two `get_fee` calls plus a
  `retrieve_documents` call to answer an amend-vs-renew comparison) is
  the explicit point, not an edge case. Every tool call — name,
  arguments, order, result — is logged per turn as both an audit trail
  and a demo artifact. Phase 6.9's citation-verification gate (structured
  output, verified against what was actually retrieved/returned)
  extends to cover tool-composed answers, not just RAG answers.
- **6.11.2 Contextual question phrasing**: `claude-haiku-4-5` rewrites
  only the intake's surface sentence — which attribute to ask next stays
  `next_question.py`'s untouched, deterministic decision. The model
  returns the rephrased text plus the attribute it believes it's asking
  about; a mismatch against the actual next attribute falls back to the
  canonical prompt, as does any generation failure. The canonical prompt
  remains what's logged, tested, and matched against an incoming answer
  — rephrasing is a presentation-only layer with no read access to
  answer-recording logic.
- **6.11.3 Visible extraction acknowledgement**: when a chat turn
  records one or more facts to `CASE_ANSWER`, the response acknowledges
  exactly those recorded facts — never an inferred or unrecorded one —
  and names any requirement newly triggered by that specific answer
  (computed by diffing the engine's resolved requirement set
  before/after the answer, not asserted by the model). An
  acknowledgement never states a fee or office; those remain tool-only,
  per 6.11.1.
- CLAUDE.md's "How the Claude API is used" job list and "Two kinds of
  question, two mechanisms" framing are updated: the open-question path
  is no longer single-shot RAG but a tool-using agent whose tools
  include RAG retrieval and read-only engine calls; the situation path
  gains two presentation-only LLM calls (rephrasing, acknowledgement)
  that touch no plan-shaped data. The rules engine remains the sole
  *producer* of plans, fees, offices, and requirements in every case —
  what changes is how many narrow jobs the API now does, not who is
  allowed to compute a citizen-facing number.

## Capabilities

### New Capabilities
- `agentic-tool-answering`: the tool-use loop over the six system-
  capability tools, the constraint that every fee/office/timeline/
  requirement value must trace to a tool result, the multi-step-chaining
  requirement for comparison questions, and the per-turn tool-call trace
  log.
- `conversational-intake`: contextual question rephrasing (with its
  attribute-mismatch and failure fallbacks to the canonical prompt) and
  visible extraction acknowledgement (recorded-facts-only, engine-
  computed triggered-requirement naming, no fee/office in the
  acknowledgement).

### Modified Capabilities
- `rag-answering`: the citation-verification requirement (6.9) is
  broadened from "generation" to "every generated response, including a
  tool-composed one" — the verification mechanism is unchanged, its
  scope is not.
- `case-resolution-data-model`: `CHAT_MESSAGE` gains a nullable
  `tool_trace` JSONB column recording that turn's tool calls (name,
  arguments, order, result) — the retrievable audit trail 6.11.1
  requires, stored alongside the message it belongs to the same way
  `cited_chunk_ids` already is.

## Impact

- `api/app/chat/tools.py` — new: the six tool definitions (JSON schemas)
  and their handler functions, each a thin wrapper over an existing
  `app.engine.*` / `app.rag.retrieval` function; no new business logic,
  no new source of truth for a fee/office/requirement.
- `api/app/chat/agent.py` — new: the `claude-sonnet-5` tool-use loop
  (call model → execute requested tool(s) → feed results back → repeat
  until a final text response), the per-turn tool-call trace log, and
  the citation-verification gate applied to the agent's final answer.
- `api/app/rag/answer.py` — `answer_question` (or its caller in
  `chat/router.py`) is rewired to invoke the new agent instead of
  Phase 5/6.7's single-shot retrieve-then-generate; `app/rag/retrieval.py`
  and `app/rag/generation.py` are unchanged in themselves — retrieval
  becomes one of the agent's tools rather than being replaced.
- `api/app/chat/rephrase.py` — new: the `claude-haiku-4-5` question-
  rephrasing call, attribute-match check, and canonical fallback.
- `api/app/chat/acknowledge.py` — new: builds the acknowledgement text
  from recorded facts and the engine's before/after requirement diff
  (`app.engine.requirements.resolve_requirements` called twice — no new
  engine logic, just two calls compared).
- `api/app/chat/router.py` — `handle_message` wires in rephrasing and
  acknowledgement around the existing record/answer flow;
  `next_question.py`'s selection logic is not touched.
- `api/app/models.py` + a new Alembic migration — `ChatMessage` gains a
  nullable `tool_trace` JSONB column.
- `api/app/chat/limits.py` — the existing 2,000-character truncation
  applies to every new call path; `max_tokens` caps added to every new
  LLM call.
- `CLAUDE.md` — "How the Claude API is used" and "Two kinds of question,
  two mechanisms" sections updated to describe the tool-using agent and
  the two presentation-only intake calls.
- `api/tests/chat/` and `api/tests/rag/` — new tests for multi-step tool
  chaining, the no-fabricated-value assertion, rephrasing fallback (both
  mismatch and API-failure paths), acknowledgement content, and
  malformed-tool-argument handling; all 89 existing tests continue to
  pass unchanged.
- No change to `api/app/engine/` itself (tools call existing functions
  read-only) or to what produces a plan, fee, office, or checklist.
