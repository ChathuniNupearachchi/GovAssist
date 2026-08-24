# GovAssist Backend — Build Plan

**Goal:** One service (Renew passport) built completely and correctly, end to end.

Ordered by dependency. Each phase consumes the previous phase's output.

---

## Phase 1 — Foundation

**1.1 Docker Compose** (`docker-compose.yml` at project root)
- Postgres 16 with pgvector (`pgvector/pgvector:pg16`), port 5432
- Redis 7 (`redis:7-alpine`), port 6379
- Named volume for Postgres data

**1.2 Python environment** — `api/venv`, requirements.txt with:
fastapi, uvicorn, sqlalchemy, alembic, psycopg2-binary, httpx,
beautifulsoup4, pdfplumber, python-dotenv, pydantic,
sentence-transformers, anthropic, celery, redis

**1.3 Folder structure**

```
api/
  main.py
  requirements.txt
  .env
  .gitignore
  alembic.ini
  migrations/
  app/
    models.py
    db/session.py
    scraper/
    ingestion/
    engine/
    rag/
    api/
```

**1.4 FastAPI skeleton** — `GET /health` returning `{"status": "ok"}`

**1.5 Database session** — engine, SessionLocal, `get_db()` dependency

**1.6 Alembic initialised** — reads DATABASE_URL from .env,
autogenerates from `app.models.Base`

**Done when:** `docker compose up -d` starts both containers and
`uvicorn main:app --reload` serves /health with 200.

---

## Phase 2 — Data model

Thirteen tables in one Alembic migration.

```
SERVICE                id, code, name, category
SOURCE_DOCUMENT        id, source_url, snapshot_path, content_hash,
                       document_type (html|pdf), fetched_at,
                       status (pending|approved|rejected)
RULE_VERSION           id, service_id, source_document_id, approved_by,
                       version_number, status (draft|approved|superseded),
                       verified_at
REQUIREMENT            id, rule_version_id, office_id, label,
                       kind (document|step|prerequisite),
                       freshness_rule, sequence
CONDITION              id, question_id, attribute,
                       operator (equals|lessThan|in), value
REQUIREMENT_CONDITION  requirement_id, condition_id, negated
FEE_RULE               id, rule_version_id, condition_id, base_amount,
                       penalty_amount, basis (normal|urgent)
QUESTION               id, service_id, prompt,
                       answer_type (single|boolean|district), sequence
OFFICE                 id, name, type (head|regional|ds|mission),
                       district, opening_hours
CASE                   id, service_id, device_ref, resolved_at, outdated
CASE_ANSWER            id, case_id, question_id, value
PLAN_ITEM              id, case_id, requirement_id, rule_version_id,
                       collected, sequence
DOCUMENT_CHUNK         id, source_document_id, chunk_text,
                       embedding vector(384), sequence
ADMIN_USER             id, email, role (reviewer|approver)
```

**Seed offices:** Head Office (Battaramulla), five regional offices
(Kandy, Matara, Vavuniya, Kurunegala, Jaffna), district to office
mapping for all 25 districts.

**Done when:** `alembic upgrade head` creates every table and every
district resolves to an office.

---

## Phase 3 — Ingestion pipeline

**3.1 Scraper** — httpx + BeautifulSoup fetches immigration.gov.lk
passport pages. Stores raw HTML with SHA-256 content hash and fetch
timestamp.
*Done when:* a snapshot is retrievable and hash-comparable across runs.

**3.2 PDF extraction** — pdfplumber pulls text from Immigration
instruction PDFs, stored with `document_type = "pdf"`.
*Done when:* text extracted from at least two instruction documents.

**3.3 Chunking** — split text into passages of roughly 200 to 400 words,
each keeping a foreign key to its source document.
*Done when:* one page produces multiple traceable chunks.

**3.4 Embedding** — sentence-transformers converts chunks to vectors,
stored in pgvector. CPU only.
*Done when:* a similarity query returns sensible results.

**3.5 LLM rule parsing** — Claude API proposes structured REQUIREMENT
and CONDITION rows. Always `status = draft`.
*Done when:* a scraped page yields draft rules for review.

**3.6 Change detection** — diff new parse against approved version.
Classify material (fee, document, office) vs cosmetic (wording).
*Done when:* an edited snapshot is correctly classified.

---

## Phase 4 — Rules engine

**Build and unit-test in isolation before any API work.**

**4.1 Condition evaluator** — evaluate one condition against a case's
answers. Operators: equals, lessThan, in. No nesting.
*Done when:* tests cover every operator plus missing-answer behaviour.

**4.2 Requirement resolver** — return requirements whose gating
conditions all pass, ordered by sequence.
*Done when:* a renewal with a name change and one without return
different, correct sets.

**4.3 Fee calculator** — LKR 10,000 normal, LKR 20,000 urgent.
*Done when:* both paths covered by tests.

**4.4 Office resolver** — urgent goes to Head Office only, otherwise
district mapping. Precedence deterministic and stated.
*Done when:* conflicting rules resolve identically every time.

**4.5 Prerequisite ordering** — photo studio acknowledgement before
application. Ordered steps, not a flat list.
*Done when:* the resolver returns a dependency-ordered plan.

**4.6 Next-question logic** — given what's known, return the next
question the engine needs. Drives the chat intake.
*Done when:* answering a question changes which question comes next.

**4.7 Golden test set** — ten renewal scenarios with hand-verified
expected outputs:

1. Straightforward adult renewal, Colombo, normal
2. Same but urgent
3. Name changed after marriage
4. Expired over 5 years ago
5. Applying from Kandy
6. Dual citizen
7. Buddhist priest
8. No longer holds old passport
9. Applying from abroad
10. Name changed and urgent and Kandy

*Done when:* the suite runs in CI and fails the build on regression.

---

## Phase 5 — RAG layer

**Prerequisite — strip navigation/footer boilerplate before chunking.**
Every page on immigration.gov.lk carries an identical ~280-word nav block
(and a repeated footer) that Phase 3's chunker currently ingests verbatim.
On a page as short as `pages_e.php?id=10`, that boilerplate fills most of
chunk 1, pushing the actual amendment fee/timeline content later in the
chunk and diluting its embedding — demonstrated directly: a similarity
query for "change my name on my passport after marriage" ranked that
chunk #6 of 25, behind several less-relevant ones. Fix this — strip nav
and footer text (e.g. by removing known block selectors, or reusing the
site's identical boilerplate as a diffable prefix/suffix to trim) before
chunking, and re-chunk/re-embed existing documents — before retrieval
quality depends on it.

**5.1 Retrieval** — embed the query, search pgvector, scoped to
approved versions only.

**5.2 Grounded generation** — Claude API answers from retrieved chunks,
citing each. If retrieval returns nothing relevant, say so.

*Done when:* "What is an authorised photo studio?" returns a grounded
answer with a source citation.

---

## Phase 6 — API routes

```
POST /chat/message             classify intent, route to engine or RAG
GET  /case/{id}/next-question  what the engine still needs
POST /case/resolve             produce the full plan
GET  /services                 list Immigration services
GET  /requirements/{id}        detail on one requirement
GET  /health                   liveness
```

Intent classification lives here — situation versus open question.

*Done when:* a full case resolves end to end through the API.

---

## Phase 6.5 sequence — Retrieval quality, generation safety, session persistence

Superseded by the sequence below: a baseline measurement, then Phases
6.6 through 6.10, implemented and measured **in order** — each phase
records its measured effect on a shared calibration set before the next
begins, so the contribution of each change can be separated. Full
proposal, spec deltas, design rationale, and task breakdown live in
`openspec/changes/phase-6-6-to-6-10-rag-quality-and-sessions/`.

**Rationale for placement.** Once Phase 7 connects the mobile app,
retrieval quality and generation safety are things a citizen sees rather
than things in a test log — fix them here, in backend context, first.

### Baseline — record before changing anything

Run and record the cosine distance for a nine-query calibration set
(six queries genuinely in the corpus, three genuinely absent) against
the current, unmodified system. Two known reference points: "What is
the fee for a name change amendment?" (0.5174) and "What are the
working hours at the Head Office?" (0.8311, worse than the absent
"How do I renew my driving license?" at 0.7358 — no single cosine
threshold separates the two). All nine are re-measured after every
phase below, in a running table in `design.md`.

### Phase 6.6 — Structure-aware chunking (do this first)

Numbered 6.6, not 6.5, because it must precede hybrid search — retuning
ranking over badly-chunked content measures the wrong thing. The
chunker currently flattens `<table>` and PDF tabular content to
undifferentiated prose, which is exactly the shape of the corpus's two
most consequential documents: the fee schedule (id=8) and the
working-hours table (id=7). Fix: detect tables during extraction
(BeautifulSoup `<table>`, pdfplumber `extract_tables()`), convert each
to markdown, splice back in document order, and never split a table
across chunks. Add a `metadata` JSONB column to `DOCUMENT_CHUNK`
(document title, section heading, content type, source URL); prepend a
compact context header to the *embedded* representation only — the
stored, citizen-facing `chunk_text` stays raw. Re-chunk and re-embed all
8 approved documents; embedding model unchanged.

*Done when:* the id=8 and id=7 tables are each one structured chunk,
every chunk carries populated metadata, the calibration set is
re-measured, and Phase 5's existing RAG tests still pass.

### Phase 6.7 — Hybrid search (vector + full-text)

Add a GIN-indexed `tsvector` column on `DOCUMENT_CHUNK.chunk_text` (no
new dependency — Postgres full-text search is built in). Blend cosine
similarity and full-text rank (`plainto_tsquery`) via reciprocal rank
fusion, which needs no tuned weight between the two signals. Approval-
only scoping and the weak-match self-check are unchanged; only the
ranking function beneath them changes. Recalibrate the accept/reject
threshold from the measured blended scores, not intuition.

*Done when:* "working hours at the Head Office" retrieves `pages_e.php
?id=7` as the top result, "driving license" returns no relevant match,
"Form K-35A" and "section 19(2)" both retrieve correctly, and all nine
calibration queries resolve correctly.

### Phase 6.8 — Embedding model upgrade (conditional)

Gated on two checks, evaluated in order, neither assumed: (1) do 6.6 and
6.7 already resolve all nine calibration queries with clear margin? If
so, stop — record the upgrade as assessed and unnecessary. (2) Is
available RAM with the full dev stack running (Docker, VS Code, dev
server) on the target ASUS VivoBook (i3-1115G4, 2 cores, 20GB installed,
no CUDA GPU) at least 6GB? `bge-base-en-v1.5` needs ~1.5–2GB resident.
If both checks pass: migrate `DOCUMENT_CHUNK.embedding` to `vector(768)`,
re-embed every chunk, verify the same model is used at ingestion and
query time, recalibrate the threshold, and re-measure the full
calibration set plus query-time embedding latency (on the citizen-
waiting critical path).

**Correction (`langgraph-orchestration-branch`, measured):** this
phase's premise assumed RAM was often tight on the target machine (a
figure of "~4GB often available" circulated in later planning for this
same phase, superseding it here). Directly measured instead, repeatedly,
across that branch's Task Groups 1–2 and its own RAM-gate task: available
RAM with the dev stack running has consistently been **~7.5–8.5GB free**
of the 20GB installed, not ~4GB, and loading `bge-base-en-v1.5` alongside
the shipped embedding model measured ~8.33GB free — the 6GB gate above
passes comfortably. RAM is not the binding constraint this phase assumed
it might be; do not cite "~4GB often available" for this machine going
forward.

### Phase 6.9 — Citation verification (anti-hallucination)

Generation is already grounded — the model sees only retrieved chunks —
but nothing verifies it actually cited what it was given. Force
generation into a structured schema via `client.messages.parse`
(`answer`, `citations: [{chunk_id, quoted_span}]`), then verify every
cited `chunk_id` is a member of the retrieved set — a set-membership
check, zero runtime cost. A citation outside that set, or an empty
citation list, triggers one retry with an explicit "cite only the
provided chunks" instruction; a repeated failure falls back to the
existing "no relevant match" response.

*Done when:* a test injecting a fabricated `chunk_id` into a mocked
model response is caught and rejected, an empty-citation answer is
rejected, all real calibration queries still produce cited answers, and
the retry path is exercised by a test.

### Phase 6.10 — Persistent session memory

`CASE_ANSWER` persists the facts, but the conversation itself doesn't
survive closing the app, and nothing consistently populates
`CASE.device_ref`. Add a `CHAT_MESSAGE` table (`id`, `case_id`, `role`,
`content`, `created_at`, `intent` nullable, `cited_chunk_ids` nullable)
persisting every message as the audit trail. The mobile app's per-device
UUID (Expo SecureStore) resolves a returning device to its most recent
unresolved case — device identified, person not. Redis caches the
active case's recent messages and answered facts with a multi-hour TTL
as a fast path; Postgres remains the durable record. A new endpoint
returns the full message history for a device's active case.

*Done when:* a case interrupted mid-intake and resumed returns both the
correct next question and the prior conversation, closing and reopening
restores the visible transcript, a device with no prior case starts
cleanly, and clearing Redis still leaves the transcript restorable from
Postgres.

### Phase 6.11 — Agentic tool calling, contextual question phrasing, and visible extraction

The open-question path (Phase 5/6.7's single-shot retrieve-then-generate)
becomes a bounded `claude-sonnet-5` tool-use loop over six read-only
tools — `retrieve_documents`, `get_fee`, `find_office`,
`get_next_question`, `resolve_case`, `compare_amendment_vs_renewal` —
each a thin wrapper over an existing engine/RAG function. The model
selects which tools to call, possibly chaining several in one turn (a
comparison question needs both services' fees, computed via two
`get_fee` calls or the dedicated comparison tool, plus a document
lookup for timelines); it never computes a fee, office, timeline, or
requirement itself — every such value in its final answer is verified
against what a tool call actually returned that turn, using the same
verify → retry-once → fall back to the explicit no-relevant-match
response shape 6.9 established for chunk citations. Every tool call —
name, arguments, order, result — is logged as a per-turn trace,
persisted on `CHAT_MESSAGE.tool_trace` (new nullable JSONB column) as
both the audit trail and the demo artifact.

Separately, the intake conversation gains two presentation-only layers,
neither touching `next_question.py`'s selection logic or what gets
recorded to `CASE_ANSWER`: a `claude-haiku-4-5` call rephrases the next
pending question's surface wording for conversational fit (falling back
to the canonical prompt on an attribute mismatch or any failure), and
another names any fact just recorded plus any requirement the rules
engine's own before/after diff shows was newly triggered by it — never
a fee or office, and never an inferred fact.

*Done when:* "Should I amend my passport or get a new one?" produces a
multi-step tool trace with both fees, both timelines, and citations,
retrievable from the transcript; a test confirms no fee/office/timeline
in any response was generated rather than returned by a tool; "My
passport expired last year" gets a contextually phrased age question
whose answer still records to `age`; a rephrasing that drifts to the
wrong attribute falls back to canonical; "I got married and my name is
different now" acknowledges the marriage certificate requirement once
the engine's diff shows it; and all rephrasing/tool-selection/malformed-
argument failure paths fall back cleanly, verified by tests.

---

## Phase 7 — Connect the mobile app

Replace mock chat in ServicesScreen with real API calls.
Replace hardcoded PlanScreen data with resolved case output.

*Done when:* a real conversation on the phone produces a real,
computed plan.

---

## Phase 8 — Supporting infrastructure

- **Redis caching** — key on case signature, invalidate on rule publish
- **Celery queue** — scraping and re-embedding off the request path
- **Nginx rate limiting** — on LLM-backed endpoints
- **OpenTelemetry tracing** — request to condition evaluation to source doc

---

## Phase 9 — Admin review console

- **JWT auth** — reviewers and approvers only
- **Version comparison** — draft versus approved, material changes highlighted
- **Approve and publish** — four consequences: write new version,
  re-embed chunks, invalidate caches, flag affected saved plans

*Done when:* changing a fee flags an existing saved plan as outdated.

---

## Phase 10 — Evaluation

**10.1 Baseline comparison** — run the ten golden scenarios through
ChatGPT with no tooling. Record accuracy on documents, fee, office.
Compare against GovAssist.

**10.2 Demo script** — three scenarios, one deliberately complex,
rehearsed under four minutes.

---

## Cut order if behind schedule

1. OpenTelemetry and Jaeger
2. Nginx rate limiting
3. Celery, collapse to FastAPI background tasks
4. Change detection (3.6)
5. Admin console, approve drafts directly in the database

**Never cut:** rule versioning, source snapshots, the golden test set,
the baseline comparison, source citations on every requirement.

---

## Workflow

Every phase starts with an OpenSpec proposal:

```
/opsx:propose <phase description>
```

Read it, approve it, then implement. Proposals land in
`openspec/changes/` as a permanent record.

---

## Database backups

The dev Postgres volume (`govassist_postgres_data`) is not durable —
it was lost outright on 2026-08-24 when Docker's disk image filled the
host drive and had to be reinstalled/relocated. Rebuilding it from
scratch (migrations + seeds + re-ingestion) is possible because the PDF
extraction cache (`api/data/snapshots/*.extraction.json`) and the
scraped content it derives from are reproducible, but a rebuild is not
free — it re-hits the live immigration.gov.lk site and burns time
re-deriving state that a backup would have preserved instantly.

**Take a `pg_dump` after every phase**, not just before something risky:

```
docker exec govassist-postgres-1 pg_dump -U govassist -d govassist > E:\govassist-backup.sql
```

Store it outside the Docker volume (E:\ here) so a repeat of the disk
failure above can't take out both the live database and its backup
together.
