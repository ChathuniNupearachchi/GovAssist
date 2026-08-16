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

## Phase 6.5 — Hybrid search (vector + full-text)

**Rationale.** Phase 5's threshold calibration showed no single cosine-
similarity cutoff separates in-corpus from out-of-corpus queries: "What
are the working hours at the Head Office?" (genuinely covered by
`pages_e.php?id=7`) scored 0.8311 — worse than "How do I renew my
driving license?" (0.7358), a topic the corpus doesn't cover at all.
Exact terms are exactly what vector search handles worst and keyword
search handles best — "Form K-35A", "section 19(2)", specific fee
amounts. Fix retrieval quality here, in backend context, before Phase 7
connects the mobile app and retrieval quality becomes something a user
sees rather than something in a test log.

**6.5.1 Full-text index** — add a `tsvector` column (or expression
index) on `DOCUMENT_CHUNK.chunk_text`, `GIN`-indexed. No new dependency
— Postgres full-text search is built in.

**6.5.2 Hybrid ranking** — combine cosine similarity and full-text rank
(e.g. reciprocal rank fusion, or a weighted blend) into one score.
Retrieval scoping (approved documents only) and the self-check/
reformulation flow from Phase 5 stay in place; only the ranking function
underneath them changes.

**6.5.3 Recalibrate** — re-run the Phase 5 threshold calibration queries
against hybrid scores, including the two that motivated this phase:
"working hours at the Head Office" should now rank above "driving
license". Record the new measured values the same way Phase 5 did —
don't assert improvement without checking.

*Done when:* "What are the working hours at the Head Office?" retrieves
`pages_e.php?id=7`, and "How do I renew my driving license?" returns no
relevant match — both correct, where cosine similarity alone had them
backwards.

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
