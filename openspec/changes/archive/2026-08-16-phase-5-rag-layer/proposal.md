## Why

Phase 4 built the rules engine for situation questions. GovAssist's other
half — open questions like "What is an authorised photo studio?" — has
no way to be answered yet: Phase 3 built ingestion and embeddings but no
retrieval or generation sits on top of them. Phase 5 closes that gap with
grounded, cited retrieval-augmented answers, while fixing a retrieval
quality defect Phase 3 already found and diagnosed (navigation/footer
boilerplate diluting embeddings) before anything depends on chunk
quality.

## What Changes

- **5.0 Prerequisite — strip boilerplate before chunking.** Every scraped
  HTML page carries an identical `<nav>` menu (128 words) and an
  identical `<section id="bottom">` quick-links/related-links/contact
  block (84 words) — 212 words of boilerplate per page, confirmed
  identical across all 5 HTML documents by direct measurement. Both are
  stripped before chunking; the existing `<footer>` (copyright/last-
  update line) is stripped too, since its date changes on every fetch
  and would otherwise churn chunk text without adding citizen-relevant
  content. PDFs are unaffected — they have no equivalent boilerplate.
  The 5 HTML documents' existing `DocumentChunk` rows are replaced
  (re-chunked and re-embedded from the stripped text).
- **BREAKING**: `SourceDocument` gains `approved_at` (nullable
  DateTime), mirroring `RuleVersion.verified_at` — a citizen-facing RAG
  answer needs a "verified as of" date and `SourceDocument` has never
  had one (only `fetched_at`, which records when it was scraped, not
  when its content was reviewed). Set when a document's status is set to
  `approved`.
- **Document approval (data, not new capability)**: no `SourceDocument`
  has ever been approved — Phase 9's admin console doesn't exist yet.
  A seed/fixture step (mirroring Phase 4's rule-version approval
  precedent) marks the first-fetch `SourceDocument` row for each of the
  8 ingested URLs (5 HTML + 3 PDF) `approved`, with `approved_at` set —
  justified because this content was already directly verified against
  the live site in Phase 3 and Phase 4. Without this, retrieval (which
  must scope strictly to `approved` documents) has nothing to return and
  this phase's own Done-When criteria can't be demonstrated.
- **5.1 Retrieval** (`api/app/rag/retrieval.py`): embed the query with
  `all-MiniLM-L6-v2` (same model as ingestion), search `DOCUMENT_CHUNK`
  via pgvector cosine distance, scoped strictly to chunks whose
  `SOURCE_DOCUMENT.status = 'approved'`. Returns top matches with each
  chunk's similarity score, source document, and `approved_at`.
- **5.3 Retrieval self-check**, built into the same module: judged by a
  cosine-similarity threshold on the top result, no extra LLM call. A
  weak top match triggers one non-LLM query reformulation (strip
  question words/stopwords, retry on the bare keywords) and one retry;
  still weak after that returns "no relevant match" rather than
  proceeding to generation.
- **5.2 Grounded generation** (`api/app/rag/generation.py`): Claude API
  (`claude-opus-5`) generates an answer from the retrieved chunks only,
  citing which chunks it used. A "no relevant match" retrieval result
  short-circuits straight to an explicit "I don't have that information"
  response — generation is never invoked on a weak or empty result, so
  it can never fabricate from noise.
- No API routes, no chat intake UI. RAG functions only, called directly
  from tests, mirroring Phase 4's "build and test in isolation" pattern.

## Capabilities

### New Capabilities
- `rag-answering`: retrieval (scoped to approved documents, with the
  self-check/reformulation behavior) and grounded generation (cited,
  refuses to fabricate) for open questions about the rules — never
  produces a plan, fee, office, or checklist.

### Modified Capabilities
- `document-chunking`: HTML text extraction excludes navigation and
  footer boilerplate before chunking.
- `case-resolution-data-model`: `SourceDocument` gains `approved_at`.

## Impact

- `api/app/ingestion/html_extraction.py` — strips `<nav>`,
  `<section id="bottom">`, and `<footer>` before extracting text.
- `api/app/models.py` — `SourceDocument.approved_at`.
- New Alembic migration adding that column.
- `api/app/seed/` — a new approval script (or extending
  `phase4_renewal.py`'s pattern) marking the 8 first-fetch documents
  approved.
- `api/app/rag/` — new package: `retrieval.py`, `generation.py`,
  `answer.py` (entry point tying retrieval, self-check, and generation
  together).
- Re-chunk/re-embed task against the 5 existing HTML `SourceDocument`
  rows (their old, boilerplate-containing chunks are deleted first).
- `api/tests/rag/` — unit tests per component plus the Done-When
  scenarios.
- No changes to the mobile app or API routes in this phase.
