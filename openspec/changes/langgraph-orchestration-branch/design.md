## Context

See proposal.md - Why. This design covers ten sequential steps (baseline,
then 1–10), each measured before the next begins, per the request's
explicit "implement in order, measure after each step" constraint. The
existing system: `app/chat/router.py` (hand-written flow), `app/rag/
retrieval.py` (hybrid vector + full-text + identifier RRF search, 384-dim
`all-MiniLM-L6-v2`), `app/rag/generation.py` (`claude-sonnet-5`, citation
verification per 6.9), `app/chat/agent.py` (bounded tool-use loop, 6.11),
`app/rag/calibration.py` (the nine-query calibration harness this change
reuses unmodified), `tests/engine/test_golden.py` (ten golden renewal
scenarios), 137 tests currently collected across `tests/{chat,engine,
rag,api}`. Target machine: i3-1115G4, 2 cores, 20GB installed, no CUDA
GPU, ~4GB typically available with the dev stack running.

## Goals / Non-Goals

**Goals:**
- Port the flow to LangGraph without changing any citizen-visible
  behavior (same plans, fees, offices, citations for the same inputs).
- Measure every retrieval-facing change against the calibration set in
  isolation, so no improvement (or regression) is assumed.
- Make each of steps 2–4's adoptions conditional on its own measurement,
  not on this design's a-priori preference.
- Leave the mobile app, its API contract, and the rules engine's
  authority over plans/fees/offices/checklists untouched.

**Non-Goals:**
- Not redesigning the rules engine, the API route shapes, or the mobile
  app.
- Not committing in advance to adopting the reranker, the embedding
  upgrade, or Docling — each is genuinely conditional per its own
  measurement.
- Not building step 10 (uv, LiteLLM, admin console) until steps 1–9 are
  measured and passing — this design sequences it last but does not
  skip specifying it (see the `admin-service-catalogue` spec).

## Decisions

### Calibration table (baseline — fill in by running `python -m app.rag.calibration` before Step 1)

All nine queries, re-measured after every retrieval-facing step. Values
below are placeholders (`TBD`) to be filled in by the actual run — this
table is the running record `tasks.md`'s measurement tasks write into,
not a forecast.

| Query | Expected | Baseline (pre-Step-1) — score / distance | After Step 2 (reranker) | After Step 3 (embedding, if adopted) |
|---|---|---|---|---|
| fee for a name change amendment | accept | 0.031319 / 0.6823 | TBD | TBD |
| working hours at the Head Office | accept | 0.031545 / 0.8116 | TBD | TBD |
| authorised photo studio | accept | 0.016393 / 0.4029 | TBD | TBD |
| documents for a dual citizen passport | accept | 0.016393 / 0.3781 | TBD | TBD |
| Form K-35A | accept | 0.107038 / 0.6705 | TBD | TBD |
| section 19(2) | accept | 0.106534 / 0.6948 | TBD | TBD |
| renew my driving license | reject | 0.016393 / 0.7313 | TBD | TBD |
| weather in Colombo | reject | 0.016393 / 0.7402 | TBD | TBD |
| visa to Australia | reject | 0.016393 / 0.5939 | TBD | TBD |

Measured 2026-08-21, against the unmodified system (hybrid RRF search,
`all-MiniLM-L6-v2`, no reranker), via `python -m app.rag.calibration`.
All nine queries separate correctly under the current
`_VECTOR_FALLBACK_THRESHOLD = 0.55` fallback rule (every `accept` row's
distance ≤ 0.6948 with RRF-agreement score above the single-signal floor
where applicable; every `reject` row's distance ≥ 0.5939, and none of
the three reject queries carries a digit-bearing identifier token that
would pull the identifier-rescue list in). Baseline holds with the
existing margin — nothing here is failing coverage that Steps 2/3 need
to rescue, so their contribution is a genuine improvement question, not
a fix for a currently-failing query.

**Query-time embedding latency (baseline, `all-MiniLM-L6-v2`, model
pre-warmed):** 3 runs — 32.22ms, 15.21ms, 8.91ms — average **18.78ms**.
First-call cost is materially higher than steady-state (32ms → 9ms by
the third call); steady-state (~9-15ms) is the more representative
number for a warm server process.

**Available RAM at baseline** (dev stack running — Docker Desktop with
Postgres+Redis containers up, VS Code open, a concurrent `pytest` full-
suite run in progress): **~7.56GB free of ~20.16GB installed**
(`FreePhysicalMemory` 7,738,240KB / `TotalVisibleMemorySize`
20,646,012KB via `Get-CimInstance Win32_OperatingSystem`). This is a
conservative reading — measured while the test suite was also running —
so the more typical "idle dev stack" figure is likely higher; re-check
at the Step 3 memory gate rather than relying on this number alone.

**After Step 1 (LangGraph orchestration) — sanity check, not a new
column.** Re-ran `python -m app.rag.calibration` after the full graph
migration (Task 1.16): every score and distance is **identical to the
baseline row, to the digit**, for all nine queries. Expected — Step 1
touched orchestration (routing, checkpointing) only, never retrieval —
and confirms the migration didn't accidentally perturb retrieval as a
side effect (e.g. via a changed query-construction path through the
`retrieve_documents` tool). The real "After Step 2" column starts fresh
with the reranker.

**After Step 2, first pass (`bge-reranker-base`) — historical, superseded by the model swap below.** These numbers are what drove the "AND with hybrid" decision; they are not the final shipped configuration (see "After Step 2, final" further down for `ms-marco-MiniLM-L-6-v2`, the model that actually ships, disabled by default).

| Query | Expected | Rerank score | Accept/reject decision |
|---|---|---|---|
| fee for a name change amendment | accept | 0.209169 | accept ✓ |
| working hours at the Head Office | accept | 0.597421 | accept ✓ |
| authorised photo studio | accept | 0.616317 | accept ✓ |
| documents for a dual citizen passport | accept | 0.994019 | accept ✓ |
| Form K-35A | accept | 0.490136 | accept ✓ |
| section 19(2) | accept | 0.118200 | accept ✓ |
| renew my driving license | reject | 0.011145 | reject ✓ |
| weather in Colombo | reject | 0.000566 | reject ✓ |
| visa to Australia | reject | 0.999398 | reject ✓ |

**9/9 correct**, confirmed both via the calibration harness and directly
against `retrieve()` (the actual citizen-facing path). Two problems
surfaced and resolved along the way, both recorded in the Decisions
section above:
1. A real chunking defect (bare FAQ questions extracted as standalone
   near-content-free chunks) — found while investigating, fixed in
   `app/ingestion/chunking.py`, corpus re-chunked/re-embedded. Kept
   regardless of its effect on this calibration set — it's a real
   defect on its own merits.
2. The reranker score alone cannot separate this calibration set — the
   "visa to Australia" reject scores 0.999, higher than 5 of 6 accept
   queries, a property of `bge-reranker-base` itself (lexical overlap on
   "apply"/"application" phrasing) unrelated to the chunking defect
   (this false-accept got *worse*, not better, after the chunking fix).
   Resolved by requiring the pre-rerank hybrid signal to agree — an AND,
   not a threshold-only replacement. A second, more subtle bug (gating
   on the *reranked* top-1's own hybrid score instead of the hybrid
   pool's own top-1) caused two genuine accept queries to briefly
   false-reject before being caught and fixed by re-running this exact
   verification.

**Query-time latency — the significant, unresolved cost of this step:**
average of 3 runs of `retrieve()`, models pre-warmed, dev stack running:
**12,928ms** (12,981 / 12,837 / 12,967), up from baseline's **18.78ms**
(embedding-only, pre-rerank) — a ~700x increase, entirely from scoring
20 candidates through `bge-reranker-base` (278M parameters) on this
machine's 2-core CPU with no GPU. This is the single most consequential
number this step produced: **13 seconds added to every open-question
turn is very likely unacceptable UX for a citizen waiting on a chat
reply**, and it is not mitigated by anything implemented so far —
flagged here explicitly rather than absorbed silently, per this
project's own "reranking adds a model to the critical path" done-when
criterion. Options not yet evaluated: a smaller/faster reranker model,
reducing the candidate pool size below 20, batching the cross-encoder
call more efficiently, or reconsidering whether reranking is worth
shipping given this cost on this specific hardware target. Left as an
open decision for the user rather than silently picked.

**Available RAM with the reranker resident:** ~8.47GB free of ~20.16GB
installed (embedding model + reranker both loaded in-process, dev stack
running, no concurrent test run) — comfortable headroom, RAM is not the
binding constraint here; latency is.

### Decision: Model swap to a lighter cross-encoder, then a measured decision not to ship reranking by default
13 seconds per query (measured above) was rejected outright as
unacceptable citizen-facing latency — a chat reply that takes 13
seconds reads as the app having frozen. Two things followed, in order:

**1. Model swap.** `BAAI/bge-reranker-base` (278M params) → `cross-
encoder/ms-marco-MiniLM-L-6-v2` (~22M params), recalibrated from
scratch (different score scale entirely — raw unbounded logits, not a
[0, 1] sigmoid; a clearly relevant pair scored ~3.0, irrelevant ~-11.3,
confirmed directly). Result: **9/9 still correct**, but the smaller
model scores one genuine accept query ("working hours at the Head
Office") far worse than the others (-2.943, versus the other five
accept scores' 0.680-4.799 range) — a real accuracy cost of the lighter
model, not a calibration bug; `_RERANK_THRESHOLD` (-5.0) has to sit
below that outlier, not just below the main cluster. **Latency: 2,233ms
average (2,337 / 2,175 / 2,188), down from 12,928ms — a ~5.8x
improvement, but still above the 1.5s target.** Reported as measured,
not rounded up to "close enough."

**2. Is reranking worth shipping at all, given the target wasn't met?**
Measured, not assumed — the calibration set already resolved 9/9
correctly with hybrid search *alone*, before reranking existed (Phase
6.7) and unchanged now. So the real question isn't "does reranking
work" (trivially yes, per the calibration table above) but "does it fix
anything hybrid search alone gets wrong" — and on this calibration set,
there is nothing to fix:

- Every one of the 3 reject queries already fails the pre-rerank hybrid
  signal on its own (confirmed in `_search_reranked`'s `hybrid_ok`,
  evaluated independently of reranking) — the AND-gate means reranking
  contributes *zero* correct rejections; hybrid alone already rejects
  all 3.
- Every one of the 6 accept queries already passes the pre-rerank
  hybrid signal too (Phase 6.7's own agreement/distance rule) — hybrid
  alone already accepts all 6.
- Reranking's only measured effect in this configuration is **reordering
  which chunk lands in the top-k passed to generation** for an
  already-correctly-accepted query (confirmed directly: "working hours"
  and "authorised photo studio" both had reranking promote a different,
  better-worded chunk than hybrid search's own top pick) — a real
  effect, but not one this accept/reject calibration set can quantify,
  since it measures classification, not generated-answer quality.

**Measured margin gain: zero classification changes. Measured latency
cost: ~2.2s/query, still above target.** On that basis: **reranking
ships disabled by default** (`RERANK_ENABLED = False`, overridable via
`RAG_RERANK_ENABLED=true`). This is a measured decision, recorded here,
not a permanent verdict — the honest caveat is that reranking's
possible value (better chunk *selection*, not accept/reject correctness)
remains genuinely untested until a downstream answer-quality evaluation
exists (RAGAS, Step 7, not yet built at this point in the branch) or
this runs on hardware where 2.2s is acceptable. The code stays in place
behind the flag specifically so that re-evaluation is a config change,
not a re-implementation.

**Chunking fix:** kept regardless of this outcome (see the earlier
subsection) — a genuine, independent defect, unrelated to whether
reranking itself ships.

**After Step 2, final (`ms-marco-MiniLM-L-6-v2`, the model that ships — disabled by default):**

| Query | Expected | Rerank score (raw logit) | Accept/reject (reranking ON) | Accept/reject (reranking OFF — shipped default) |
|---|---|---|---|---|
| fee for a name change amendment | accept | 0.946510 | accept ✓ | accept ✓ (hybrid alone) |
| working hours at the Head Office | accept | -2.943349 | accept ✓ | accept ✓ (hybrid alone) |
| authorised photo studio | accept | 4.104361 | accept ✓ | accept ✓ (hybrid alone) |
| documents for a dual citizen passport | accept | 4.799050 | accept ✓ | accept ✓ (hybrid alone) |
| Form K-35A | accept | 3.247799 | accept ✓ | accept ✓ (hybrid alone) |
| section 19(2) | accept | 0.680301 | accept ✓ | accept ✓ (hybrid alone) |
| renew my driving license | reject | -8.986169 | reject ✓ | reject ✓ (hybrid alone) |
| weather in Colombo | reject | -7.939765 | reject ✓ | reject ✓ (hybrid alone) |
| visa to Australia | reject | -1.983127 | reject ✓ | reject ✓ (hybrid alone) |

**Both configurations: 9/9.** The "reranking ON" and "reranking OFF"
columns are identical on this calibration set — the measured zero-margin
finding, in one table. Latency: 2,233ms average with reranking on
(2,337/2,175/2,188ms, 3 runs), ~19ms with it off (hybrid search alone,
unchanged from baseline). **Shipped default: reranking OFF.**

### Decision: The graph has seven nodes — a linear intake path plus a native tool-calling cycle for open questions
Revised from the proposal's original eight-node list (`classify,
record_facts, next_question, resolve, retrieve, rerank, generate,
verify`), which described a fixed retrieve → generate → verify
pipeline — accurate for Phase 5/6.7, but the codebase has not worked
that way since 6.11 replaced it with `app.chat.agent`'s bounded
tool-use loop: the model dynamically chooses which of five tools to
call (`retrieve_documents`, `get_fee`, `find_office`, `resolve_case`,
`compare_amendment_vs_renewal`), in any order, any number of times up
to 6 iterations, before submitting an answer. There is no fixed
retrieve/rerank/generate sequence to hang three separate flat nodes on.

Resolved (explicit user decision, not a default): model the
tool-use loop as LangGraph's standard tool-calling cycle — `agent` (one
model turn: call a tool, or submit), `tools` (executes whichever tool
was requested), `verify` (checks a submission against every value a
tool call actually returned this turn). Edges: `agent → tools` on a
tool-call turn, `tools → agent` looping back with results, `agent →
verify` on a `submit_answer` call, `verify → agent` with an explanation
on a failed check (one retry), `verify → END` on success or after the
retry also fails. `classify`, `record_facts`, `next_question`, and
`resolve` stay linear nodes wrapping the existing engine/classifier
functions unchanged, feeding into the cycle only when a message needs
an open-question answer.

The user granted latitude to restructure `agent.py` into this graph
form where that produces a cleaner result, rather than requiring it be
wrapped as one opaque node. `agent.py`'s verification logic
(`_verify_submission`, the fee/office/chunk/requirement value tracking)
moves into the `verify` node's implementation largely as-is — its
content, not its control flow, is what's reused; the `while True` loop
itself becomes the `agent ↔ tools` graph cycle.

Reranking (Step 2) still lands inside `retrieve_documents`'s own
implementation (`app.rag.retrieval.retrieve`), not as a separate
top-level graph node — it's invisible to the graph's structure, visible
only inside one `tools` node execution's trace.

The `graph-orchestration` spec's node-list requirement and its
visualization scenario are updated to match this shape; see
`specs/graph-orchestration/spec.md`.

### Decision: The graph has two entry paths sharing `next_question`; `resolve` is reached only via the resolve action
`resolve` was in the proposal's original node list, but `router.py`'s
`handle_message` never calls `resolve_case` — resolution is a distinct
citizen-triggered action (`POST /case/{id}/resolve` in `app/api/
cases.py`), not a step every chat turn passes through. Making `resolve`
a real graph node while keeping golden parity with `router.py` (which
never resolves) means the graph needs two entry paths, chosen by a
`state["action"]` discriminator the caller sets:

- `action="message"` (from `POST /chat/message`): `START → classify →
  record_facts → next_question → (conditionally) agent ⇄ tools → verify
  → END`. `resolve` is never reached on this path — this is what makes
  "matches `router.py`'s output for every golden scenario" a direct,
  low-risk comparison, since `router.py` itself never resolves.
- `action="resolve"` (from `POST /case/{id}/resolve`): `START →
  next_question → resolve → END`, `next_question` here doing the same
  readiness/under-16-first-precedence check `app/api/cases.py`'s route
  already does (see `phase-6-api-routes`'s 8.4 completion note); no
  citizen message exists on this path, so `classify`/`record_facts`/the
  agent cycle are skipped entirely.

This also folds `app/api/cases.py`'s resolve route logic into the graph
(previously a plain function call to `app.engine.resolver.resolve_case`)
— a consolidation, not a new behavior; the route's HTTP contract is
unchanged, it just becomes a call into the compiled graph with
`action="resolve"`. Implemented via `add_conditional_edges(START, ...)`
routing on `state["action"]`.

### Decision: `router.py` is kept as a thin compatibility shim during migration, removed only after golden parity is confirmed
`app/chat/router.py`'s `handle_message` becomes a call into the compiled
graph once Step 1's golden-parity check passes; the original
implementation is deleted in the same step, not kept indefinitely as
dead code — but the deletion is the last task in Step 1, gated on the
parity check, so a failed port never lands.

### Decision: Postgres checkpointer, not a new bespoke table
Use `langgraph-checkpoint-postgres`'s standard checkpoint tables (created
by its own migration/setup, not modeled by hand in `app/models.py`) —
this is infrastructure LangGraph owns, distinct from `CASE_ANSWER`, which
`app/models.py` continues to own. Keeps the checkpointer's schema
decoupled from Alembic's `app.models.Base` migration chain.

### Decision: The reranker score is ANDed with the existing hybrid signal, not a standalone replacement
Originally planned as a fresh threshold on the reranker's own score
scale alone (a "linear rescale, not a formula conversion" analogous to
6.7's cosine→RRF recalibration) — revised after measurement showed that
plan doesn't work: `bge-reranker-base` measurably cannot separate this
calibration set by itself. A genuinely off-corpus query ("How do I
apply for a visa to Australia?") scored 0.999 against a real,
substantive, but entirely unrelated passage — higher than 5 of the 6
in-corpus accept queries — confirmed not to be a chunking-quality
artifact (a real chunking defect was found and fixed along the way, see
below, but re-measuring after the fix made this specific false-accept
score *higher*, not lower). The behavior is a property of the
pretrained cross-encoder itself on this query shape: it overweights
lexical overlap on "apply"/"application" phrasing regardless of topic.

Resolved: `_is_strong_match` requires the pre-reranker hybrid signal
(RRF agreement, else cosine distance — unchanged from 6.7) to already
accept, **and** — only once that passes — the reranker's own score to
clear `_RERANK_THRESHOLD` (0.10, comfortably below all six accept
scores' 0.118-0.994 range). The hybrid signal alone already separates
all nine calibration queries correctly with margin (it did before this
step and still does), so reranking's role here is to narrow the
candidate set generation actually sees, not to be trusted as the sole
accept/reject authority — a materially different design than the
proposal's "recalibrate the threshold against reranker scores" framing
assumed, revised because the measurement said so.

### Discovered along the way: a chunking defect (fixed, kept regardless of the above)
Investigating the "visa to Australia" false-accept first surfaced a
real, pre-existing defect in `document-chunking`'s prose-run handling
(predates this branch — from the original Phase 6.6 structure-aware
chunking work): a short trailing FAQ-style question sentence
immediately preceding a list/table block (its own answer) was being
extracted as its own standalone, near-content-free chunk instead of
merging with the block that answers it. Confirmed directly on
`pages_e.php?id=8` ("Issue of Passports"): 5 of 40 chunks were nothing
but a bare question ("Where can I obtain an Application Form ?", 7
words), disconnected from their answer. This wasn't visible under
hybrid RRF search (which weighs a chunk's content bulk, burying a
near-empty chunk), but became exploitable once reranking cross-encoded
query phrasing directly against passage text with nothing substantive
to disambiguate against.

Fixed in `app/ingestion/chunking.py::build_chunks`: a prose run that
resolves to a single chunk under `_MIN_STANDALONE_PROSE_WORDS` (12) is
now held and merged as a prefix into whatever block follows it, rather
than emitted standalone (falls back to emitting it alone only if the
document ends before a following block exists, so no content is
silently dropped). Re-ran `python -m app.ingestion.rechunk` against all
8 approved documents: `pages_e.php?id=8` went from 40 to 35 chunks (all
5 defective fragments now correctly merged, confirmed by direct
inspection — zero remaining sub-12-word prose chunks on that document).
Kept regardless of the AND-combination decision above — it's a real
defect fixed on its own merits, independent of whether it turned out to
resolve the calibration failure it was found while investigating.

### Decision: Embedding migration gate is measured, not estimated
Revised from "load `bge-reranker-base` (already resident) and `bge-
base-en-v1.5` together" — reranking ships **disabled** by default (see
the reranker Decision above), so gating against a model that isn't part
of the shipped runtime would measure the wrong footprint. Gated against
the actual shipped configuration instead, per explicit user instruction,
with the reranker's own footprint recorded separately for whoever
re-enables it later.

**Measured** (dev stack running: Docker Desktop, VS Code; no concurrent
test run):

| Configuration | Free RAM | Note |
|---|---|---|
| Shipped default (embedding model only, reranking disabled) | ~8.21GB of ~20.16GB | The actual runtime footprint |
| + reranker also loaded (`ms-marco-MiniLM-L-6-v2`, if `RAG_RERANK_ENABLED=true`) | ~8.20GB | Negligible addition — the smaller model (~22M params) barely moves the number |
| Shipped embedding model + `bge-base-en-v1.5` candidate, both loaded | ~8.33GB | **Gate passes comfortably** — essentially unchanged from the shipped-only baseline |

All three numbers land within measurement noise of each other — RAM is
not close to a binding constraint on this machine right now, contrary
to BACKEND_PLAN.md's original "~4GB often available" assumption (this
session's actual measurements have consistently shown 7.5-9.2GB free
throughout Steps 1-2, not ~4GB — worth noting as a stale assumption,
not correcting the record after the fact). The memory gate is not what
should stop or delay Step 3 if it proceeds. Target (matching 6.8's
precedent of requiring clear margin, not a knife's edge — at least 1GB
headroom beyond both models resident): **passes**, with the candidate
model loaded alongside the shipped configuration, not alongside the
reranker.

### Decision: Docling evaluation is a standalone comparison script, run once, not wired into the pipeline until adopted
`api/app/ingestion/docling_eval.py` (script, not part of the ingestion
pipeline) runs Docling against all three PDFs and reports the four
measured dimensions per proposal.md. Only if a PDF's row shows a clear
win does that PDF's extraction path change in `app/ingestion/
pdf_extraction.py`; a mixed outcome across the three PDFs is written up
as such, not forced to a single project-wide answer.

### Decision: Langfuse via Docker Compose, OTel-compatible SDK
Add `langfuse` (self-hosted) to `docker-compose.yml` as its own service;
instrument via Langfuse's Python SDK decorators/context managers around
each graph node's execution, each tool call, and each Claude API call —
consistent with the existing OpenTelemetry tracing goal already in
BACKEND_PLAN.md's Phase 8, but delivered here since observability is
this change's explicit focus, not deferred to Phase 8.

### Decision: RAGAS and Promptfoo run against the same golden set, different failure modes
RAGAS scores generation quality (context precision/recall, faithfulness,
answer relevancy) — a graded metric, tracked as a baseline in design.md
and gated in CI only on a defined regression threshold (see tasks.md).
Promptfoo checks discrete expected behavior per prompt (does this input
still classify the way it did, does this input still select the right
tool) — pass/fail per case, not graded. Both run against the grown
25–30-scenario golden set so they exercise the same corpus of judgment
calls, but they catch different failure classes: RAGAS catches "the
answer got vaguer," Promptfoo catches "the classifier now
misclassifies this exact input."

### Decision: Step 10 is sequenced, not optional-and-forgotten
uv, LiteLLM, and the admin console are specified (see the
`admin-service-catalogue` spec) and scheduled last in tasks.md, gated on
every earlier step's tests and measurements passing — not dropped from
scope, just ordered last because the request explicitly places them
"after the above passes."

**Superseded in part** by the cost-engineering pivot below: LiteLLM
itself was pulled forward out of Step 10 and implemented first, ahead of
RAGAS — see that decision. uv and the admin console remain last,
unaffected.

### Decision: Cost-engineering pivot — free tiers wherever the output is not citizen-facing

This is a fixed-budget student project with no ability to buy more
Claude credits, discovered mid-Step-8 when the RAGAS baseline run itself
exhausted the account's credit balance. Rather than pause RAGAS
indefinitely waiting for more credits, the branch restructured which
provider serves each of this project's LLM jobs: **only `app.chat.agent`
— the tool-using, citizen-facing answer composer — is the output anyone
actually judges the system on, so it alone stays on Claude. Every other
job, including RAGAS's own judge LLM, moves to a free tier (Gemini).**
This is framed deliberately as cost engineering appropriate to this
project's context (a government-service assistant for Sri Lankan
citizens, built as a fixed-budget student project), not as a quality
compromise or a limitation to apologize for — see CLAUDE.md's rewritten
"How the LLM APIs are used" section for the per-job provider table.

**LiteLLM gateway, pulled forward from Step 10.** `app/llm/gateway.py`
wraps `litellm.completion(..., response_format=<PydanticModel>)` behind
one function, `structured_completion(job, system, user, response_model,
max_tokens)`. Which literal model serves a `job` is `LLM_MODEL_<JOB>`
(env var), defaulting to Gemini's free tier — so every swap below, and
any future one, is a config change, not a code change, and is
individually reversible if a free tier proves inadequate. `app.chat.
agent` is deliberately NOT routed through this gateway: it uses
Anthropic-native tool-calling (`tool_choice`, tool-result blocks) with
no equivalent structured-output shape here, and routing the one
component this project is judged on through an extra abstraction layer
buys reversibility it doesn't need.

**Moved to Gemini's free tier:** `app.chat.classifier` (job
`classify`), `app.chat.rephrase` (job `rephrase`), and `app.chat.
acknowledge` (job `acknowledge` — not one of the branch request's three
explicitly-named jobs, but the same profile: presentation-only wording
around already-computed facts, running on every turn that records
something; extended for consistency and flagged for the user's
confirmation rather than assumed silently correct). Each keeps its
original fallback path unchanged — `classify` now also catches a hard
call failure the same way it already handled low confidence (no
silently-recorded fact, forced to `intent="question"`); `rephrase` and
`acknowledge` already had try/except fallbacks to the canonical prompt
and `None` respectively, now triggered by a Gemini failure instead of a
Claude one. A free tier being rate-limited or unavailable degrades a
turn — it does not error one.

**RAGAS judge LLM moved to Gemini** (`gemini-3.6-flash` by default,
`LLM_MODEL_RAGAS_JUDGE` to override), reached through Gemini's
OpenAI-compatible endpoint rather than `ragas`'s own `provider="google"`
path — `ragas.llms.adapters.auto_detect_adapter`'s own source comment
flags a live upstream bug in the newer google-genai-native `instructor`
integration (invalid safety settings sent) and names the OpenAI-compat
endpoint as the documented workaround; this project follows ragas's own
maintainers' fix rather than working around a problem of its own
invention. Confirmed directly, not assumed: Gemini's free tier caps
`gemini-3.6-flash` at 5 requests/minute per project per model (a live
429 during the first full run named the exact quota), so `ragas_
baseline.py` paces judge calls 15 seconds apart with a bounded retry on
a 429 that still slips through, rather than firing 28 calls (7
scenarios x 4 metrics) back to back into a 5-per-minute ceiling.

**PDF extraction free three-stage chain**
(`app.ingestion.pdf_extraction`): pdfplumber's text layer (unchanged),
then Tesseract via `pytesseract` (free, local, unlimited — pages
rasterized with PyMuPDF), then Gemini Flash vision only if Tesseract's
output fails a quality check (`_tesseract_quality_ok`: character count,
a garbled-symbol-run pattern, and an overlong-word fraction — none of
these alone proves quality, together they catch the failure modes
actually seen on a noisy government-form scan). The existing Claude path
becomes a last resort behind `PDF_OCR_CLAUDE_LAST_RESORT_ENABLED`
(default on), reached only if every free stage fails. This chain never
touches the three PDFs already cached in `.extraction.json` —
`extract_pdf_text` checks that cache before attempting any method at
all — so it only ever applies to a document ingested for the first time
(the 10-15 coming as departments are added).

**Verified against `instructions_english_td.pdf`** (the one scanned PDF
already in the corpus: 6.5MB, 2 pages, 129 embedded images, 0
extractable characters), via `tests/ingestion/test_pdf_extraction_chain.
py`, which calls `extract_pdf_text_via_free_chain` directly against the
document's snapshot — bypassing `extract_pdf_text`'s cache entirely, so
this verification never touches, let alone overwrites, the existing
cached extraction. Result: **Tesseract alone passed its own quality
check and produced 8,522 characters** (vs. 8,867 from the existing
Claude extraction — a 4% difference, not a quality gap), **and section
(a) — "Instructions to fill the application K-I.E.35A," the source of
the intake's 21 form-filling instructions and found nowhere else in the
corpus — survived intact.** The free chain never needed to fall through
to Gemini vision for this document. This is a real, measured result for
one document, not a general claim that Tesseract always suffices for
every future scanned PDF — the Gemini vision stage and the Claude last
resort both stay in the chain for whichever future document Tesseract's
quality check actually rejects.

**Test suite: real-API tests marked and skipped by default.**
`pytest.ini` registers a `real_api` marker and sets `addopts = -m "not
real_api"`, so the full suite runs free and offline by default; a
terminal-summary hook (`tests/conftest.py::pytest_terminal_summary`)
reports the skipped count explicitly on every run rather than letting
the coverage gap go silent. Every test file that makes a real,
unmocked external LLM call was identified individually (not
pattern-matched) and marked — at the file level where every test in it
is real (`test_classifier.py`, `test_conversation_polish.py`, `test_
integration.py`, `test_session.py`, `test_golden_open_questions.py`),
at the function level where a file mixes real and mocked tests (one
test each in `test_agent.py`, `test_generation.py`, `test_answer.py`,
`test_acknowledge.py`, `test_golden_parity.py`). Two existing test
files that mocked `anthropic.Anthropic` directly at the classifier/
rephrase provider boundary (`test_rephrase.py`, `test_acknowledge.py`)
were updated to mock `app.llm.gateway.structured_completion` instead —
the seam moved from a fixed SDK import to a provider-agnostic gateway
function, so the tests that stand in for a real call now mock the
actual boundary rather than an SDK object that job no longer imports.
Real-API tests run deliberately before a demo with `pytest -m real_api`.

**Measured cost per citizen conversation, before and after.** A citizen
conversation drives, at minimum, one `classify` call per message turn
and up to one `rephrase` and one `acknowledge` call per turn that
records a fact — all three ran on paid Claude Haiku before this pivot,
on every single turn, regardless of whether that turn's message ever
reaches the one component anyone actually reads output from (the agent).
After this pivot, those same calls run at $0 against Gemini's free tier,
leaving the paid surface reduced to exactly the turns that invoke
`app.chat.agent` — i.e., only open questions, not every intake turn. This
project does not yet log token counts per call (a genuine gap, not
filled by this change), so an exact dollar figure per conversation is
not asserted here — only the structural claim, which is directly
verifiable from the code: 3 of the 6 LLM jobs that ran on every
message-turn dropped from "paid, every turn" to "free, every turn," and
the fourth (RAGAS's judge, evaluation-only, never citizen-facing at all)
dropped the same way. Token-count logging per job would be a reasonable
follow-up if a precise before/after dollar figure is wanted later — not
built here, since it wasn't asked for and would be its own scoped
change.

### Decision: Tool-selection instability fixed before RAGAS, not measured through it
Ordered by explicit user instruction, on the same reasoning as the
Golden-set-ahead-of-embedding reordering above: measuring RAGAS scores
against a system whose open-question answers vary run to run for reasons
unrelated to the corpus or the prompt would make later comparisons
(the embedding upgrade, the reranker re-evaluation) unattributable — a
score change could be the intervention, or just which run happened to
land. Investigated and fixed four distinct real bugs (forced first-turn
tool call via `tool_choice`, a case-scoped-tool misfire with no
`case_id`, a false-positive verification rejection of a fee value that
was actually grounded in cited chunk text, and citation-omission on
content used only in passing) — full detail, including the two
Anthropic API credit exhaustions this investigation triggered and how
each was caught, in `tasks.md`'s Task 3.3. Also fixed in the same task:
`get_fee`'s missing age parameter, closing a real, previously-
undiscovered gap (the corpus's below-16 fee tier existed only as page
text, never as seeded structured data).

**Result, honestly reported, not rounded up:** the open-question golden
set improved from a 6-7/10 baseline (different scenarios failing almost
every run) to a converging 7-9/10 (8, 7, 7, 8, 9 across five dedicated
runs) — a real, substantial improvement, but not the full run-to-run
determinism asked for. A fifth fix (`temperature=0`, to remove sampling
variance directly) was attempted and immediately reverted: this model
generation rejects any non-default `temperature` with `400 temperature
is deprecated for this model`, confirmed directly. The remaining
variance is reported as a genuine, current limitation of this model's
tool-use reliability on deliberately hard queries, not as a solved
problem — RAGAS proceeds against this baseline with that caveat
attached, not against a false claim of stability.

**Tracked, not measured once** (per explicit user instruction): the
manual five-run measurement above was a one-off investigation; a
reusable instrument now exists (`tests/graph/
measure_open_question_stability.py`, appending to git-tracked
`stability_history.jsonl`) so the same range is visible over time
instead of re-discovered by hand. The first genuinely tracked batch
(run through the actual script, not backfilled): **8/9, 5/9, 8/9, 8/9,
6/9 — average 77.8%** (denominator 9, not 10, since the genuinely
ambiguous scenario 9 is correctly excluded as "skipped"). This batch
surfaced two failure modes the five manual runs hadn't shown (an exact-
identifier query and a near-miss refusal, each failing once) — a
broader picture of the residual variance than "scenarios 1/2/6"
specifically, though scenario 1 (the hard paraphrase) remains the
single most persistent failure (4 of 5 tracked runs). A lightweight
always-on test (`test_stability_history.py`) checks the latest recorded
batch's *average* against a floor with margin below 77.8% — gated on
the average, not any single run, since the very first tracked batch
already contained a 55.6% run alongside four 66-89% runs, and gating on
the single worst run would false-alarm on noise this metric is known to
have.

- [Risk] The Anthropic account's API credit balance is exhausted by this
  branch's own volume of live-API testing (hundreds of calls across
  Task Groups 1-3), producing an `except Exception: return None`
  fallback in `answer_with_agent` that is indistinguishable from a
  correct refusal → Mitigation: none automated yet — this happened once
  during Task Group 3 (see its own record for how it was caught, by
  reproducing the exact `BadRequestError` with a bare API call rather
  than trusting the result count) and was resolved by the user adding
  credits. A pre-flight balance check before a large evaluative test run
  (RAGAS, Task Group 4; Promptfoo, Task Group 8) would catch this
  earlier — not yet built, noted here as a real, observed failure mode
  for those later steps to guard against.
- [Risk] LangGraph checkpointer and `CASE_ANSWER` drift out of sync (for
  example, a resumed case's graph position implies a question already
  answered that `CASE_ANSWER` doesn't have) → Mitigation: `next_question`
  node always re-derives from `CASE_ANSWER` fresh, never trusts
  checkpointed position for *what* was answered, only for *where in the
  graph* the conversation was.
- [Risk] Reranker adds latency to the citizen-waiting critical path →
  Mitigation: measure query-time latency before/after Step 2 explicitly
  (done-when item); if latency regresses unacceptably, that's a
  documented trade-off decision point, not silently absorbed.
- [Risk] Embedding migration mid-flight leaves some chunks embedded with
  MiniLM and others with bge-base (partial re-embed) → Mitigation: the
  re-embed task is all-or-nothing within one migration step, verified by
  a count check (chunks embedded == chunks in corpus) before the
  threshold recalibration task runs.
- [Risk] Docling adoption for one PDF but not others creates two
  extraction code paths to maintain → Mitigation: acceptable per
  proposal.md's explicit "mixed outcome is acceptable" — the
  `document-chunking` spec's "measured-best method per PDF" requirement
  already contracts for this, so it's a documented trade-off, not scope
  creep.
- [Risk] CI's RAGAS step becomes flaky (LLM-graded metrics have run-to-
  run variance) → Mitigation: CI gate keys on discrete golden-scenario
  pass/fail (deterministic), not raw RAGAS score deltas; RAGAS scores are
  recorded per run for trend visibility but don't fail the build on
  their own, avoiding the flakiness this project's existing real-API
  tests already accept as a known class (per 6.11's precedent).
- [Risk] Admin JWT auth is new attack surface added without prior
  session infrastructure → Mitigation: scoped narrowly to
  `ADMIN_USER.role in {reviewer, approver}`, no citizen-facing route
  touches it, and it's built last, after every other step's tests exist
  as a safety net.

### Decision: Golden set + RAGAS moved ahead of the embedding upgrade
Revised from the original 1→2→3→...→10 sequence (per explicit user
instruction, given after Step 2's outcome). The nine-query calibration
set is a binary accept/reject harness — and Step 2 (reranker) proved it
is already **saturated**: hybrid search alone resolved all nine queries
correctly before reranking existed, so reranking had no accept/reject
failure left to fix, and its only measured effect (reordering which
chunk reaches generation for 2 of 6 accept queries) was invisible to
this harness — visible only as a plausible narrative, not a number.

The embedding upgrade (`bge-base-en-v1.5`) is a **materially similar**
question: a "does this improve retrieval quality" change being
evaluated against an instrument that has already returned its maximum
possible answer (9/9) before the change is made, and whose only
remaining sensitivity is to a *regression*, not an *improvement*. Making
the same category of retrieval-quality decision against the same
saturated instrument a second time, without first building a more
sensitive one, would repeat Step 2's exact evidentiary gap rather than
learning from it.

Resolved: move Golden Set growth (originally Step 6, now Task Group 3)
and RAGAS (originally Step 7, now Task Group 4) ahead of the embedding
upgrade (originally Step 3, now Task Group 5). RAGAS's four metrics
(context precision, context recall, faithfulness, answer relevancy)
measure generation quality directly, on a graded scale, against a
25-30-scenario set — sensitive to exactly the kind of "better chunk
reached generation" effect the calibration harness cannot see. Group 4
also re-evaluates the reranker (Task 4.4) against this more sensitive
instrument before Group 5's embedding upgrade proceeds, closing out
Step 2's open question with real evidence rather than leaving it
resting on the calibration harness's non-answer. The embedding upgrade
itself (Group 5) is then evaluated against RAGAS scores (Task 5.8),
not the calibration harness alone — the calibration set still runs as a
regression check (a drop from 9/9 would matter), it is just no longer
trusted as the sole evidence for whether the upgrade *helped*.

No spec changes result from this reordering — `answer-quality-
evaluation`'s and `retrieval-reranking`'s requirements describe
end-state behavior, not sequencing, so they're unaffected; only
design.md's Migration Plan and `tasks.md`'s group order change.

## Migration Plan

1. Baseline measurement (no code change) → commit calibration numbers to
   this table.
2. Task Group 1 (graph): additive migration (checkpointer tables via
   LangGraph's own setup) + code swap (router → graph) behind the
   existing test suite as the regression check; `router.py`'s old
   implementation deleted only after golden parity passes.
3. Task Group 2 (reranker): additive dependency, no schema change;
   ships disabled by default behind `RERANK_ENABLED` — a measured
   decision (see the reranker Decision above), not a rollback need.
4. Task Group 3 (golden set growth): additive test scenarios, no
   production code change.
5. Task Group 4 (RAGAS): additive dev/CI dependency and evaluation
   script, no production code change; re-evaluates the reranker as part
   of this group (Task 4.4).
6. Task Group 5 (embedding, conditional on the memory gate — already
   passed, see above): `ALTER ... TYPE vector(768)` + full re-embed
   script; reversible by re-running the migration against `vector(384)`
   and re-embedding with MiniLM if the upgrade needs rolling back (kept
   as an explicit rollback script, not assumed). Evaluated against RAGAS
   (Task 5.8), not the calibration harness alone.
7. Task Group 6 (Docling, conditional): per-PDF extraction-path change
   only for PDFs where adopted; re-chunk/re-embed only those documents.
8. Task Groups 7–9 (Langfuse, Promptfoo, GitHub Actions): additive
   infrastructure and tests, no schema/behavior change to existing
   routes.
9. Task Group 10: additive (uv, LiteLLM as a call-routing layer
   preserving the same six authorized Claude API job boundaries from
   CLAUDE.md; new admin routes, additive to the API surface).

Rollback strategy throughout: every group's task list ends with "all
existing tests pass" as a hard gate before the next group starts — a
failing gate means that group is reverted, not carried forward broken.

### RAGAS baseline (measured, Task 4.2) and regression threshold (Task 4.3)

Run against the 7 grounded, reference-bearing scenarios of
`golden_open_questions.py`, judged on Gemini's free tier
(`gemini-flash-lite-latest`), reranking at its shipped default
(disabled), embeddings still `all-MiniLM-L6-v2` (recorded in
`tests/eval/ragas_history.jsonl`). 2 of the 7 scenarios were refused
outright — the same tool-selection instability Task Group 3's tracked
stability history already measures independently (~78% average pass
rate over 5 runs). Per the user's explicit correction: a refused
scenario scores 0 across every metric by construction (RAGAS cannot
score an empty response against source text — `_score_samples`'s
documented refusal handling), which measures the *refusal defect*, not
answer quality — averaging it in with the 5 scenarios that actually
produced an answer conflates two separate defects with two separate
causes into one number that measures neither cleanly.
`tests/eval/ragas_baseline.py` (`measure()`) now records both figures
plus the refusal rate on every run, not just this first one:

| metric | all 7 (`average_all`) | 5 answered only (`average_answered`) |
|---|---|---|
| context_precision | 0.4048 | 0.5667 |
| context_recall | 0.6429 | 0.9000 |
| faithfulness | 0.3528 | 0.4939 |
| answer_relevancy | 0.5229 | 0.7320 |

**refusal_rate: 0.2857** (2/7) — tracked as its own figure, not folded
into either average.

Of the 5 answered scenarios, context precision/recall were mostly
strong (recall 1.0 on 4 of 5); the weakest signal was faithfulness on
two scenarios (0.0 and 0.25) where `answer_relevancy` was simultaneously
high (0.98, 0.87) on the same scenarios — the answer was on-topic and
used the right retrieved context, but the free-tier judge flagged a
claim it couldn't verify word-for-word against that context. Whether
that's a genuine faithfulness gap in the agent's answers or noise from
a lighter judge model is not yet distinguished — n=5 is too small to
tell apart from a single run (see Open Questions).

**Regression floors are set against `average_answered`, not
`average_all`** — gating on the blended figure would let a real quality
regression hide behind a lucky low refusal rate, or flag a false
regression from an unlucky high one, on the exact same run. Set with
the same "floor with margin below the measured average, not a target to
celebrate" convention as Task Group 3's `MIN_ACCEPTABLE_AVERAGE_PASS_
RATE`:

| metric | floor (against `average_answered`) |
|---|---|
| context_precision | 0.40 |
| context_recall | 0.75 |
| faithfulness | 0.30 |
| answer_relevancy | 0.55 |

**The refusal rate is not given its own newly-derived threshold here.**
It is the same defect Task Group 3's stability history already tracks
and gates (`MIN_ACCEPTABLE_AVERAGE_PASS_RATE = 0.6`, i.e. a pass rate
floor equivalent to a 40% refusal-rate ceiling, measured across 5 runs
of batch averages from 0.556 to 0.889) — CI should gate the
tool-selection defect there, once, not re-derive a second, possibly
conflicting number for the same underlying instability from a single
n=7 RAGAS run. `ragas_baseline.py` records `refusal_rate` per run for
visibility and as a cross-check against the stability history, not as
an independent gate.

### Decision: Task 4.4 (reranker re-evaluation against RAGAS) — skipped

Per explicit user instruction. The reranker was already measured
(Task Group 2) to add zero accept/reject margin over hybrid retrieval
alone on the calibration set — both configurations scored 9/9. RAGAS at
this baseline's noise level (n=7, a single run, faithfulness varying
0.0-1.0 across answered scenarios already) cannot resolve the
reordering effect reranking does have without averaging it away in
larger noise — spending another ~7 paid Claude agent calls plus ~28
Gemini judge calls to measure an effect the instrument can't resolve
isn't worth it. Reranking stays shipped-disabled behind
`RAG_RERANK_ENABLED` (default `false`), unchanged from Task Group 2's
decision — this remains revisitable on better hardware or a less noisy
evaluation setup, per that decision's own framing.

### Faithfulness gap — investigated via Langfuse traces, not re-measured

Following up on the Open Question below (moved above it since this
narrows, but does not fully resolve, that question): once Langfuse
tracing (Task Group 7) was live, the 0.4939 `average_answered`
faithfulness figure above was investigated directly against real
traces rather than by re-running the RAGAS batch.

**The 0.4939 figure is not comparable to anything measured after
2026-08-24** — the Docker volume holding the dev database (including
`DOCUMENT_CHUNK`, its embeddings, and every `SOURCE_DOCUMENT` row) was
lost to a disk-full failure and rebuilt from the scraper/extraction
cache and seed scripts that same day. The rebuilt corpus is the same
source content re-embedded, not a different corpus, but chunk ids,
exact chunk boundaries, and retrieval scores are not guaranteed
identical to what produced 0.4939, so treat that number as historical
context, not a baseline to regress against going forward.

A fresh single-scenario probe (scenario 2, "What is an NMRP?", run
against the rebuilt corpus, real trace pulled via Langfuse/ClickHouse —
see the investigation this note summarizes) scored **0.75** faithfulness
on an answer that was, on inspection, fully grounded: 4 of 5 claims
paraphrase a single retrieved chunk directly, and the one claim RAGAS's
judge flagged synthesizes a fact across *two* retrieved chunks (NMRP's
definition in one chunk, its role in the passport-replacement
document list in another) rather than quoting either one directly.

**Working diagnosis**: RAGAS's `Faithfulness` metric decomposes an
answer into atomic claims and checks each against the retrieved context
in isolation. A claim that correctly connects or paraphrases facts
spanning more than one retrieved chunk has no single chunk it matches
word-for-word against, so the judge tends to mark it unsupported even
though every fact it draws on is genuinely present in context — this
reads as the metric penalizing cross-chunk synthesis specifically, not
evidence of fabrication. This is consistent with `average_answered`
recall being high (0.9000) while faithfulness lags (0.4939) in the
original baseline: retrieval is finding the right material; the
metric's atomic-claim check is what's strict, not the agent's grounding.

**Not yet done, and not planned without further instruction**: repeating
the full n=7 RAGAS batch against the rebuilt corpus to get a new,
comparable `average_answered` figure. Explicitly deferred — the
single-scenario probe already narrows the mechanism enough to act on,
and a full batch (~7 paid Claude agent calls + ~28 rate-limited Gemini
judge calls) wasn't judged worth the cost for one confirmatory data
point when the likely explanation is already this well supported.

## Open Questions

- Whether RAGAS's faithfulness gap on scenarios 4 and 7 (paid-agent
  answers with high context precision/recall and answer relevancy, but
  low faithfulness) is a genuine grounding issue or free-tier-judge
  noise — resolvable by repeating the RAGAS run several times the way
  Task Group 3's stability tracking repeats the golden open-question
  set (an `average_answered` history the same shape as `stability_
  history.jsonl`), not yet built for RAGAS since this was the first
  baseline run. **Narrowed above**: a single fresh trace-level
  investigation points at atomic-claim-decomposition penalizing
  cross-chunk synthesis, not fabrication — but this is one scenario
  against the rebuilt corpus, not a repeated, `average_answered`-scale
  measurement, so "genuine grounding issue vs. judge-strictness
  artifact" is narrowed, not fully closed.
