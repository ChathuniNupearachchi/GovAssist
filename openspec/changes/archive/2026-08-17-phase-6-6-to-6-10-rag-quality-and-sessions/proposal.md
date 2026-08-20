## Why

Phase 5's retrieval is structure-blind and threshold-blind at once: the
chunker flattens tables into undifferentiated prose (the fee schedule
and the working-hours table are the two most consequential pieces of
content in the corpus), and no single cosine cutoff separates in-corpus
from out-of-corpus queries — "working hours at the Head Office" (in
corpus) scores *worse* (0.8311) than "how do I renew my driving
license" (absent, 0.7358). Generation is grounded in retrieved chunks
but nothing verifies the model actually cited what it was given, so a
fabricated citation would pass silently. And the conversation itself
doesn't survive a closed app, even though the engine remembers every
fact through `CASE_ANSWER` — a returning citizen sees an empty chat.
Fix all four here, in that order, while it's still a test-log problem —
Phase 7 connects the mobile app next, at which point a citizen sees the
consequences directly.

## What Changes

- **Baseline measurement**: before any implementation, the nine-query
  calibration set (six in-corpus, three absent) is run against the
  current system and its cosine distances recorded in `design.md` as
  the reference row every later phase's row is compared against.
- **6.6 Structure-aware chunking**: HTML `<table>` elements and PDF
  `extract_tables()` output are converted to markdown and spliced back
  in document order instead of being flattened to prose by
  `extract_text()`/`get_text()`; a table is never split across chunks.
  Every chunk gains a `metadata` JSONB column (`document_title`,
  `section_heading`, `content_type`, `source_url`); a compact context
  header (`Document: … / Section: … / Source: …`) is prepended only to
  the text that gets embedded, never to the stored `chunk_text` citizens
  see. All 8 approved documents are re-chunked and re-embedded with the
  existing embedding model.
- **6.7 Hybrid search**: a `tsvector` column on `DOCUMENT_CHUNK.chunk_text`
  (GIN-indexed) backs a `plainto_tsquery` full-text search that runs
  alongside the existing pgvector cosine search; the two rankings are
  blended by reciprocal rank fusion. Approval-only scoping and the
  weak-match self-check are unchanged — only the ranking function
  beneath them changes. The accept/reject threshold is recalibrated
  against the blended scores using the measured calibration data, not
  intuition.
- **6.8 Embedding model upgrade (conditional)**: migration to
  `bge-base-en-v1.5` (768 dims) proceeds only if both hold: (1) 6.6/6.7
  leave calibration queries unresolved with clear margin, and (2)
  available RAM with the full dev stack running is measured at 6GB or
  more. Both checks, and the outcome, are recorded in `design.md`
  whether or not the migration proceeds. No spec delta is included for
  this phase in this proposal — see Design's note on why.
- **6.9 Citation verification**: generation is forced into a structured
  schema (`answer`, `citations: [{chunk_id, quoted_span}]`) via
  `client.messages.parse`. After generation, every cited `chunk_id`
  SHALL be a member of the set of chunks actually passed to the model;
  a citation outside that set triggers one retry with an explicit
  instruction to cite only the provided chunks, then falls back to the
  existing "no relevant match" response. An answer with an empty
  citation list is treated as a failure, not a valid grounded answer.
- **6.10 Persistent session memory**: a new `CHAT_MESSAGE` table
  persists every message in and out (role, content, intent, cited chunk
  ids) as the durable audit trail. The mobile app's per-device UUID
  (already sent per `case-api`) is used to resolve a returning device to
  its most recent unresolved case. Redis caches the active case's recent
  messages and answered facts with a multi-hour TTL as a fast path;
  Postgres remains the durable record. A new endpoint returns the full
  message history for a device's active case so the app can restore the
  visible transcript on reopen — not just the engine's resolved facts.
- CLAUDE.md's RAG layer section and Claude API jobs list are updated
  where this change affects them (hybrid ranking, structured/verified
  generation output).

## Capabilities

### New Capabilities
- `chat-session-persistence`: persists every chat message, resolves a
  returning device to its most recent unresolved case, keeps a Redis
  hot-session cache alongside the Postgres durable record, and exposes
  transcript restoration — so a returning citizen sees their prior
  conversation, not just an engine that silently remembers facts.

### Modified Capabilities
- `document-chunking`: table-aware extraction (HTML and PDF) replaces
  flattening tables to prose; chunks gain populated metadata; the
  embedded representation carries a context header that the stored,
  citizen-facing `chunk_text` does not.
- `rag-answering`: retrieval ranking changes from cosine-only to a
  reciprocal-rank-fusion blend of vector and full-text search, with a
  recalibrated accept/reject threshold; generation gains a citation
  verification gate — a citation outside the retrieved set or an empty
  citation list is rejected, with one retry before falling back to the
  existing no-relevant-match response.
- `case-resolution-data-model`: `DOCUMENT_CHUNK` gains a `metadata`
  JSONB column and a GIN-indexed `tsvector` expression over
  `chunk_text`; a new `CHAT_MESSAGE` table is added. (The Phase 6.8
  embedding-dimension change, if it proceeds, is out of scope for this
  proposal's delta — see design.md.)

## Impact

- `api/app/ingestion/` — HTML table detection and PDF `extract_tables()`
  handling; chunker gains metadata population and context-header
  construction for the embedded representation only.
- `api/app/rag/retrieval.py` — hybrid ranking (vector + full-text via
  reciprocal rank fusion), recalibrated threshold.
- `api/app/rag/generation.py` — structured output via
  `client.messages.parse`, verification gate, retry-once-then-fallback.
- `api/app/models.py` + a new Alembic migration —
  `DOCUMENT_CHUNK.metadata` (JSONB), `DOCUMENT_CHUNK` `tsvector`
  GIN index, new `CHAT_MESSAGE` table.
- `api/app/chat/` and `api/app/api/` — device-based case resolution,
  message persistence on every turn, new transcript endpoint; Redis
  hot-session read/write around the existing case flow.
- Re-chunking and re-embedding scripts run once against all 8 approved
  documents (6.6), and again if 6.8 proceeds.
- `openspec/changes/phase-6-6-to-6-10-rag-quality-and-sessions/design.md`
  — calibration table, appended to after every phase.
- `CLAUDE.md` — RAG layer section (hybrid ranking, metadata-enriched
  chunks) and Claude API jobs list (structured, verified generation
  output).
- No change to the rules engine (`api/app/engine/`) or to what produces
  a plan, fee, office, or checklist — RAG's role stays advisory-only.
