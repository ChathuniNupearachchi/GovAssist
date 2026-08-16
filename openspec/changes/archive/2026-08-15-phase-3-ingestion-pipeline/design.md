## Context

`api/app/scraper/` and `api/app/ingestion/` are empty packages (created in
Phase 1, populated with models to write to in Phase 2). See proposal.md
for the site research this design is grounded in: the target is five
pages (`pages_e.php?id=7,8,9,10` and `studio_e.php`) and three instruction
PDFs, since immigration.gov.lk has no dedicated renewal page and a name
change can resolve as either an amendment or a full renewal. All
dependencies (httpx, beautifulsoup4, pdfplumber, sentence-transformers,
pgvector) are already installed from Phases 1–2 — nothing new to add.

**Update, discovered during implementation**: `instructions_english_td.pdf`
is a scanned document — confirmed via direct inspection (6.5MB, 2 pages,
129 embedded images, 0 extractable characters on page 1). `pdfplumber`
cannot get usable text from it; no PDF-text-layer library can, since
there is no text layer. See the Claude API fallback decision below.

**Update, discovered during implementation**: the five HTML pages embed a
live visitor counter in the page footer, which changes on every fetch.
Confirmed by diffing two consecutive fetches of `pages_e.php?id=7`
(6 seconds apart): the entire 32,386-byte page was byte-identical except
for the counter digits (`73408471` → `73414156`). This means
`content_hash` changes on every fetch of these pages, even when the
actual requirement content is unchanged — see the Risks section below.

## Goals / Non-Goals

**Goals:**
- Fetching the target pages/PDFs persists a raw, hashed, timestamped,
  `pending` snapshot before any parsing.
- Re-running the scraper produces a comparable hash (same hash if
  unchanged, different if changed) — proving the hash is deterministic
  and stored, not that a skip-if-unchanged decision is made.
- Extracted text from at least two PDFs, chunked into ~200–400 word
  passages, each traceable to its source document.
- Chunks are embedded locally (CPU-only, 384 dimensions) and support a
  similarity query.

**Non-Goals:**
- No LLM rule parsing (BACKEND_PLAN.md 3.5) — chunks are stored; nothing
  reads them to propose `Requirement`/`Condition` rows yet.
- No change detection (3.6) — this change stores a comparable hash; it
  does not decide "skip this fetch, nothing changed" or classify a diff
  as material vs cosmetic. Every run inserts a fresh `SourceDocument` row.
- No reviewer/approval workflow or admin console — nothing in this change
  ever sets `status` to anything but `pending`.
- No linkage from `SourceDocument` to a `Service` row — Phase 2's
  `Service` table exists, but wiring "this document is about the renewal
  service" is deferred to whichever phase actually needs that join (rule
  parsing, most likely). This phase's documents are identified by URL,
  not by a service foreign key.
- No retrieval endpoint or "approved-only" query filtering — that's
  `rag-retrieval`, a future capability. This change's chunks are
  queryable by anyone with DB access; nothing citizen-facing reads them.
- No age- or eligibility-based content filtering — the target pages
  contain full under-16 passport requirements alongside adult ones, and
  this pipeline ingests and chunks all of it uniformly. Deciding what
  applies to whom is Phase 4's job (rules engine, scoped to adult
  applicants in v1); this phase only has to make sure the under-16
  content is actually ingested and retrievable for Phase 4 to scope
  around later — verified directly in this change's own tasks, not
  assumed.
- No OCR for image-heavy pages within an otherwise-text PDF, and no
  partial-page fallback — the Claude API fallback triggers per-document,
  only when `pdfplumber` extracts zero usable text for the whole
  document. A PDF that's mostly text with one scanned diagram uses
  `pdfplumber` alone in this phase.

## Decisions

**Raw snapshots are saved to disk under `api/data/snapshots/`, named by
content hash** (`{content_hash}.html` / `{content_hash}.pdf`), with
`SourceDocument.snapshot_path` storing that relative path. Naming by hash
means re-fetching identical content overwrites the same file path with
identical bytes (a no-op), while changed content naturally gets a new
file — the snapshot files themselves end up content-addressed, on top of
the hash already being stored as its own column.
- Alternative: store raw bytes in the database (a `bytea`/`Text` column).
  Rejected — `SourceDocument`'s Phase 2 schema has no such column
  (`snapshot_path` was deliberately a path, not inline content); adding
  one now would be a schema change this proposal doesn't scope.

**Extracted text is never persisted as its own column — chunking reads
directly from the saved snapshot file (BeautifulSoup for HTML,
pdfplumber for PDF) and only the resulting chunks are stored.** Matches
Phase 2's actual `SourceDocument` schema (no `raw_content` or
`extracted_text` column exists) and keeps "the snapshot is the audit
trail" literally true — there's exactly one persisted copy of the
original content, not a second lossy derivative sitting alongside it.

**Each fetch always inserts a new `SourceDocument` row; nothing checks
the previous hash to decide whether to skip or update.** That decision
("is this a material change?") is explicitly BACKEND_PLAN.md 3.6. Here,
"hash-comparable across runs" means: query two rows for the same
`source_url` and compare their `content_hash` — the comparison is
available, not automated.

**Rate limiting is a fixed delay between requests (no token-bucket
library)**, appropriate for this phase's actual request volume — five
pages plus three PDFs, eight requests total. A more sophisticated limiter
is unwarranted complexity at this scale; revisit if a future phase
scrapes at real volume.

**User-Agent identifies the project by name and purpose**, e.g.
`GovAssist-Ingestion/1.0 (+https://github.com/<org>/govassist; automated
ingestion for a citizen document-checklist app)`. The exact contact
URL/email is a placeholder to fill in with a real, monitored address
during implementation — not fabricated here.

**Chunking splits on whitespace-tokenized word count (200–400 words),
preferring to break at paragraph boundaries when one falls inside that
range**, rather than a hard mid-sentence cut. Chunk boundaries are
otherwise an implementation detail the spec deliberately doesn't pin
down further (same reasoning as the earlier, unsynced RAG-layer
proposal's chunking design).

**Embedding model is `sentence-transformers`'s `all-MiniLM-L6-v2`**
(384-dimension output — matches the `vector(384)` column Phase 2 already
created; no dimension mismatch to reconcile). CPU-only, no GPU
dependency, consistent with CLAUDE.md's constraint.

**Similarity search for the Done-when criterion is verified with an
ad-hoc pgvector cosine-distance query (`embedding <=> :query_vector`),
not a built endpoint.** Building a real retrieval endpoint is
`rag-retrieval`'s job (unsynced, future capability); this phase only
needs to prove the embeddings are usable.

**Scanned PDFs fall back to the Claude API for text extraction, not
Tesseract/OCR.** When `pdfplumber` extracts no usable text from a PDF
(confirmed for `instructions_english_td.pdf` — see Context), extraction
falls back to sending the PDF directly to the Claude API, which reads
scanned documents natively. `anthropic` is already a pinned dependency
(Phase 1) — no new package to add, and no system-level binary to install,
which matters on Windows. This is the fourth of CLAUDE.md's narrow Claude
API jobs (updated alongside this change — see CLAUDE.md's "How the
Claude API is used"): OCR-by-LLM, not a citizen-facing generation job.
Its output flows through the same chunking/embedding pipeline as any
other extracted text. Scanned PDFs are common in Sri Lankan government
sources generally, not just this one file — this fallback will recur
beyond Immigration.
- Alternative: `pytesseract` + a Tesseract system binary. Rejected — a
  real, awkward-on-Windows system dependency for a project that otherwise
  installs nothing beyond Python packages and Docker.
- Alternative: treat scanned PDFs as an accepted gap, same as
  `studio_e.php`. Rejected by the user — `instructions_english_td.pdf`
  contains form-filling instructions (section (a)) that exist nowhere
  else in this change's scope and map directly onto Phase 4's intake
  questions.

**Extraction method and result are cached per content hash**, in
`api/data/snapshots/{content_hash}.extraction.json`
(`{"method": "pdfplumber" | "claude-api", "text": ..., "model": ...,
"extracted_at": ...}`). Two reasons: auditability (which method actually
produced a document's text is recorded, not assumed), and cost control
(re-running ingestion against unchanged content doesn't re-call the paid
Claude API — the cache is checked before falling back).
- Alternative: no caching, re-extract every run. Rejected — would
  silently re-spend on every re-run of the pipeline against unchanged
  content, and gives no auditable record of which method produced a
  given document's text.

## Risks / Trade-offs

- [The five HTML pages embed a live visitor counter that changes on every
  fetch, so `content_hash` never matches across fetches even when the
  actual requirement content is unchanged — confirmed by diffing two
  consecutive fetches of `pages_e.php?id=7` (identical except for the
  counter digits)] → the hashing mechanism itself is correct and verified
  in isolation (SHA-256 is deterministic on identical bytes); this is a
  site characteristic, not a pipeline defect. Accepted as a known
  limitation for this phase — "hash-comparable across runs" means the
  comparison is available and the hash is deterministic, not that this
  specific site's hash is expected to be stable. Flagged explicitly as a
  real constraint for Phase 3.6 (change detection): raw-byte hashing of
  these pages will register a "change" on every single run regardless of
  real content changes, so that phase will need to normalize out volatile
  elements (the counter, and whatever else surfaces) or hash extracted
  text rather than raw HTML. Not solved here — that's explicitly 3.6's
  job, not this phase's.
- [immigration.gov.lk's HTML structure or any of the five page/three PDF
  URLs can change or go offline between this proposal and implementation]
  → the scraper targets are config constants (URL strings), not hardcoded
  deep in parsing logic, so redirecting to a corrected URL is a one-line
  change, not a redesign. If a page is gone entirely at implementation
  time, that's a blocker to report, not to route around by inventing
  content.
- [`studio_e.php`'s studio listing appears to load dynamically — a plain
  `httpx` GET returns the page shell (district dropdown, empty
  "Authorized Studios List" table) rather than real studio rows, likely
  because studio data is fetched per-district via JS/AJAX or a
  server-side filter this pipeline's static fetch doesn't drive] →
  accepted as a known limitation for this phase: the page is still
  fetched, hashed, and snapshotted like any other target (satisfying this
  change's own Done-when criteria, none of which test studio-routing
  specifically), but it may not yield usable studio-to-district data yet.
  Getting real studio data (finding the underlying data endpoint, or
  driving the dropdown) is follow-up work, not silently treated as done
  here.
- [Extracted HTML text will likely include navigation/footer boilerplate
  that pdfplumber-only PDFs won't have] → acceptable for this phase; the
  Done-when criterion is "a similarity query returns sensible results,"
  not "chunks are boilerplate-free." Cleanup is a quality improvement for
  a later pass, not a blocker now.
- [`studio_e.php`'s content, if any studio rows are actually present, is
  tabular (Studio Name / Address / Tel No per district) — word-count-based
  chunking can split a table awkwardly, separating a studio's name from
  its own address/phone/district] → accepted for this phase's generic
  chunking approach; table-aware chunking is a refinement for whichever
  phase actually depends on precise studio-to-district retrieval quality.
- [Content-addressed snapshot filenames mean two different `SourceDocument`
  rows for the same unchanged URL point at the same file] → intentional
  (see decision above), and harmless: the file is immutable once written,
  so sharing it across rows is not a correctness risk.
- [No `Service` linkage means these documents aren't yet queryable as
  "renewal service documents" without knowing the URL] → acceptable per
  Non-Goals; deferred to whichever phase adds that join.
- [Calling the Claude API during ingestion costs money per scanned
  document, unlike the free local `pdfplumber` path] → mitigated by the
  extraction cache: a given content hash is only ever sent to Claude
  once. Only matters at scale if scanned-PDF volume grows significantly —
  acceptable at this phase's scale (one scanned PDF).
- [Claude API extraction of a scanned PDF is not deterministic/byte-exact
  the way `pdfplumber`'s text-layer extraction is] → acceptable: this
  pipeline's spec requires extracted text to exist and be
  chunkable/retrievable, not to be a verbatim transcription; the original
  PDF bytes remain the audit trail via the snapshot, unaffected by which
  extraction method was used.

## Migration Plan

1. Implement the scraper (`api/app/scraper/`): fetch, hash, snapshot,
   persist `SourceDocument` (html) — for each of the five target pages.
2. Implement PDF extraction (`api/app/ingestion/`): fetch, hash,
   snapshot, persist `SourceDocument` (pdf), for each of the three
   instruction PDFs.
3. Implement chunking (`api/app/ingestion/`): read a snapshot, extract
   text (falling back to the Claude API when `pdfplumber` yields nothing
   usable, cached per content hash), split into chunks, persist
   `DocumentChunk` rows.
4. Implement embedding (`api/app/ingestion/`): load the local model once,
   embed chunk text, write `DocumentChunk.embedding`.
5. Run the full pipeline against all five real target pages and three
   PDFs; verify each Done-when criterion directly (re-fetch for hash
   comparison, count chunks per document, run similarity queries
   including one targeted at under-16 content).

No existing ingested data — this is the first time anything writes to
`source_document` or `document_chunk` outside of Phase 2's own migration
tests.
