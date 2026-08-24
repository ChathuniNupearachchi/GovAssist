## Why

The chat flow's routing (`app/chat/router.py`) is hand-written Python
calling the deterministic pass, classifier, engine, and RAG in sequence.
That's worked through Phase 6.11, but it has no visualizable structure,
no per-node tracing, no checkpointed conversation position independent
of `CASE_ANSWER`, and retrieval quality has plateaued at hybrid
vector+full-text search with no reranking or evaluation harness beyond
the nine-query calibration set and ten golden scenarios. This change
ports the flow onto LangGraph for structure and observability, adds an
optional reranking stage and (conditionally) an embedding upgrade to
retrieval, evaluates Docling against the current PDF pipeline without
assuming it wins, adds Langfuse tracing, grows the golden set and adds
RAGAS/Promptfoo/CI gates, and — only once all of that passes — adds
tooling swaps (uv, LiteLLM) and an admin CRUD console. Every retrieval-
facing step is measured against the existing nine-query calibration set
before and after, in isolation, so its individual contribution is never
assumed.

**Ordering, revised mid-implementation:** the golden set and RAGAS work
originally sequenced after the embedding upgrade were moved ahead of it
once the reranking step (implemented first) showed why that order was
backwards — the nine-query calibration set is a binary accept/reject
harness that hybrid search alone already saturates at 9/9, so it cannot
detect an *improvement* from either reranking or an embedding upgrade,
only a regression. Reranking's real, measured effect (reordering which
chunk reaches generation for some queries) was invisible to that
harness; evaluating the embedding upgrade against the same saturated
instrument would repeat that evidentiary gap. RAGAS, which grades
generation quality on a continuous scale against a larger scenario set,
is what can actually tell the two apart — so it's now built and used to
re-evaluate the reranker's shipped-disabled default, and to evaluate the
embedding upgrade, before the embedding migration itself proceeds. See
design.md's "Golden set + RAGAS moved ahead of the embedding upgrade"
decision for the full record.

## What Changes

- Port `router.py`'s turn-handling flow to a LangGraph `StateGraph` with
  linear nodes `classify`, `record_facts`, `next_question`, `resolve`,
  plus a native tool-calling cycle for open questions — `agent` (one
  model turn: call a tool or submit), `tools` (executes the selected
  tool), `verify` (checks a submission against what tools actually
  returned this turn, one retry on failure) — replacing the original
  fixed retrieve/rerank/generate/verify pipeline this proposal first
  assumed, since Phase 6.11 already replaced that pipeline with a
  dynamic multi-tool agent loop before this change started (see
  design.md's revised Decision). Conditional edges are deterministic
  Python functions — no LLM output selects the next node. Add a
  LangGraph Postgres checkpointer for conversation position, alongside
  `CASE_ANSWER` (which remains the sole store of facts the engine
  evaluates), not replacing it. Export the graph visualization.
- Add a reranking stage (`bge-reranker-base`, self-hosted, CPU) between
  hybrid retrieval and generation: hybrid search returns 20 candidates,
  the reranker scores each against the query, top 5 go to generation.
  Recalibrate the weak-match threshold against the reranker's score
  scale (distinct from cosine distance / RRF score).
- Conditionally migrate embeddings from `all-MiniLM-L6-v2` (384-dim) to
  `bge-base-en-v1.5` (768-dim), gated on measured available RAM with the
  reranker already loaded (needs ~1.5–2GB more, machine typically has
  ~4GB free of 20GB installed, no GPU). If the measurement fails the
  gate, defer and keep MiniLM — an explicitly acceptable outcome, not a
  fallback to hide.
- Evaluate Docling against the current pdfplumber + Claude-vision-
  fallback pipeline on all three corpus PDFs, per PDF, on character
  count, table structure preservation, extraction time, and content
  present in one method but not the other — with particular attention
  to `instructions_english_td.pdf` (6.5MB scan, 129 images, zero
  extractable text layer), whose current Claude-vision output (8,867
  characters) contains the 21 form-filling instructions that exist
  nowhere else in the corpus. Adopt per-PDF only where it measurably
  wins; a mixed outcome (Docling for some PDFs, current pipeline for
  others) is an acceptable result, not a partial failure.
- Add self-hosted Langfuse (Docker Compose) tracing every LLM call, tool
  call, and graph node transition, linked to `case_id`.
- Grow the golden set from 10 to 25–30 hand-verified scenarios: renewal
  branches, general questions, exact-identifier queries, and
  out-of-corpus queries that must be refused.
- Add RAGAS (context precision, context recall, faithfulness, answer
  relevancy) against the golden set, and Promptfoo regression testing
  for the classifier, agent, and rephrasing prompts.
- Add a GitHub Actions CI pipeline running pytest plus RAGAS as a merge
  gate, with Postgres and Redis as service containers, external-API
  tests marked and skipped with skips reported.
- Only after the above passes: replace pip with uv, add a LiteLLM
  gateway in front of Claude API calls, and add JWT-authenticated admin
  CRUD routes for the service catalogue (requirements, conditions,
  fees, offices).

**BREAKING**: none of the above changes any existing API response shape,
mobile app contract, or rules-engine output. The mobile app (React
Native/Expo) is unchanged — no work happens there.

## Capabilities

### New Capabilities
- `graph-orchestration`: the LangGraph `StateGraph` replacing
  `router.py`'s hand-written flow — deterministic conditional edges (the
  model never selects graph routing), a Postgres checkpointer for
  conversation position alongside (not replacing) `CASE_ANSWER`, and an
  exportable graph visualization.
- `retrieval-reranking`: the two-stage retrieval pipeline (hybrid search
  → reranker → generation) and the reranker-scale weak-match threshold,
  layered on top of `rag-answering`'s existing retrieval and citation
  behavior.
- `observability-tracing`: self-hosted Langfuse tracing of every LLM
  call, tool call, and graph node transition, linked to `case_id`.
- `answer-quality-evaluation`: the grown golden set (25–30 scenarios),
  RAGAS metrics against it, and the CI gate that fails a merge on golden
  scenario regression.
- `prompt-regression-testing`: Promptfoo regression coverage for the
  classifier, agent, and rephrasing prompts.
- `admin-service-catalogue`: JWT-authenticated CRUD routes for editing
  requirements, conditions, fees, and offices — built only after every
  prior capability in this change is passing.

### Modified Capabilities
- `rag-answering`: retrieval's ranking requirement gains the reranker
  stage (20 hybrid candidates → reranked → top 5), and the weak-match
  requirement's threshold is recalibrated against the reranker's score
  scale instead of the RRF/cosine scale.
- `document-chunking`: the embedding requirement is generalized from a
  hardcoded 384-dimension model to "one configured local CPU model, used
  identically at ingestion and query time, whose dimension the schema
  matches" — covering the conditional `bge-base-en-v1.5` migration — and
  the PDF-extraction requirement is generalized to "the measured-best
  method per PDF, defaulting to the current pdfplumber + Claude-vision
  pipeline," covering the conditional Docling adoption.
- `case-resolution-data-model`: the chunk-persistence requirement's fixed
  384-dimension scenario is generalized the same way, so the schema-level
  contract matches whichever embedding model `document-chunking`
  currently configures.

## Impact

- New code: `api/app/graph/` (StateGraph, nodes, checkpointer wiring,
  visualization export), `api/app/rag/rerank.py`, Langfuse client
  wiring across `api/app/chat/` and `api/app/rag/`, `api/app/ingestion/`
  changes for any adopted Docling path, `api/app/api/admin.py` (last).
- Modified: `api/app/chat/router.py` (superseded by the graph, kept or
  removed per design.md's decision), `api/app/rag/retrieval.py`
  (reranking stage, threshold), `api/app/ingestion/embedding.py`
  (conditional model swap), `api/app/models.py` +
  Alembic migration (`DOCUMENT_CHUNK.embedding` to `vector(768)`,
  conditional; LangGraph checkpointer tables).
- New dependencies: `langgraph`, `langgraph-checkpoint-postgres`,
  reranker weights (`bge-reranker-base`), conditionally
  `bge-base-en-v1.5`, `langfuse`, `ragas`, `promptfoo` (Node-based, CI
  only), conditionally `docling`, and in step 10 only: `uv`, `litellm`.
- Infra: `docker-compose.yml` gains a Langfuse service;
  `.github/workflows/` gains a CI pipeline with Postgres/Redis service
  containers.
- Test suite: all currently-collected tests (137, spanning
  `tests/chat`, `tests/engine`, `tests/rag`, `tests/api`) must keep
  passing after every step; the golden set grows from 10 to 25–30 within
  `tests/engine/test_golden.py`'s existing pattern.
- Mobile app (`govassist/`): unaffected — no screens, API contracts, or
  state changed.
