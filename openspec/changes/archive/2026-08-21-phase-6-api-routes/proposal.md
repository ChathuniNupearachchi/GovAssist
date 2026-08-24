## Why

Phases 4 and 5 built the rules engine and RAG layer as isolated,
directly-tested Python functions — nothing outside a test file could
reach them. Phase 6 makes them reachable over HTTP and adds the one
piece neither phase built: the routing that decides, for a given
citizen message, whether the rules engine or RAG answers it. This is
"Two kinds of question, two mechanisms" (CLAUDE.md) made real at the
API boundary.

## What Changes

- **6.1 Intent classification** (`api/app/chat/`): a deterministic first
  pass matches an obvious answer to the case's pending question (by
  type — a district name, a number, yes/no) with no API call. Otherwise
  a Claude Haiku 4.5 call classifies the message into `intent`
  (situation/question/answer), `extracted` facts keyed by condition
  attribute, and `contains_question`. Low confidence defaults to
  `question`, leaving the pending question unanswered — a wrongly
  answered question is a minor annoyance; a silently missed fact
  produces a wrong plan. A message that is both a situation and a
  question is handled in one turn: extracted facts are recorded, the
  question is answered via RAG, and the pending question is re-asked.
  The classifier never returns a fee, office, or requirement.
- **6.2 Input limits**: every citizen message is truncated to 2,000
  characters before it reaches any model call, on every route that
  accepts free text.
- **6.3 Routes** (`api/app/api/`): `POST /chat/message`,
  `GET /case/{id}/next-question`, `POST /case/{id}/resolve`,
  `GET /services`, `GET /requirements/{id}` — wired to the existing
  `app.engine` and `app.rag` functions, none of which change their own
  behavior in this phase.
- **BREAKING (implementation only, not spec)**: grounded generation
  (Phase 5's `app/rag/generation.py`) switches from `claude-opus-5` to
  `claude-sonnet-5`, per this phase's explicit instruction. Generation's
  spec (`rag-answering`) never named a model, so this is a code change,
  not a spec change — no requirement is modified.
- CLAUDE.md's "How the Claude API is used" job #2 is reworded from
  "Matching a free-text situation to a service" to describe what it
  actually now does: classifying a message's intent, extracting facts,
  and detecting an embedded question. Still job #2, not a new fifth
  job — this phase's classifier is what that job always meant to become
  once there was a live chat surface to drive it.

## Capabilities

### New Capabilities
- `intent-classification`: the deterministic-then-Claude routing that
  turns a citizen chat message into recorded facts, a routed question,
  or both — never a plan, fee, office, or requirement.
- `case-api`: the HTTP surface over the rules engine and RAG layer —
  request/response shapes, citation propagation, and the boundary that
  keeps RAG from ever answering with plan-shaped data.

### Modified Capabilities
(none — the rules engine and RAG behavior specs are unchanged; only new
capabilities sit in front of them)

## Impact

- `api/app/chat/` — new package: `deterministic.py` (type-appropriate
  matchers per pending question), `classifier.py` (Claude Haiku 4.5
  structured-output call), `router.py` (ties both together, decides
  what to record vs. what to answer via RAG).
- `api/app/api/` — new routers: `chat.py`, `cases.py`, `services.py`,
  `requirements.py`; `main.py` updated to mount them alongside the
  existing `/health`.
- `api/app/rag/generation.py` — `MODEL` constant changes to
  `claude-sonnet-5`.
- `CLAUDE.md` — job #2's description reworded (see above).
- `api/tests/chat/` and `api/tests/api/` — unit tests for classification
  and integration tests for the routes, including the full
  message→questions→resolve flow.
- No changes to `api/app/engine/`, `api/app/rag/retrieval.py`, or any
  Phase 2–5 schema.
