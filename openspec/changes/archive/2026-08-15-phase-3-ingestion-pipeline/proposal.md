## Why

BACKEND_PLAN.md Phase 3 turns the empty schema from Phase 2 into actual
data: without a scraped, chunked, embedded source document, the rules
engine (Phase 4) has nothing to cite and the RAG layer (Phase 5) has
nothing to retrieve. This change builds the first four of Phase 3's six
steps — scraper, PDF extraction, chunking, embedding — scoped to the
passport renewal service and its real decision branches. LLM rule parsing
(3.5) and change detection (3.6) are explicitly later changes.

**Scoping research done before writing this proposal, corrected after
initial review**: immigration.gov.lk has no dedicated "renewal" page, so
renewal-relevant content is spread across five pages:

- `pages_e.php?id=7` — General Information (photo studio requirements,
  fingerprints, offices, hours, validity)
- `pages_e.php?id=8` — Issue of Passports (documents, fees, timelines,
  minor and dual-citizen rules)
- `pages_e.php?id=9` — Overseas Applications
- `pages_e.php?id=10` — Amendments (alterations including name change,
  LKR 1,200, 1 hour 30 minutes — confirmed by fetch)
- `studio_e.php` — Authorized Photo Studios (needed to route a citizen to
  a studio in their district)

`pages_e.php?id=11` (Passport Support Services — certification and Arabic
translation) is deliberately excluded: unrelated to renewal.

**Why `id=10` is in scope**: a name change after marriage can be handled
as an amendment (LKR 1,200, 1h30m) instead of a full renewal (LKR 10,000,
30 working days). That's a real decision branch the rules engine must be
able to surface, so its source has to be ingested now, not bolted on
later.

Three instruction PDFs are the PDF-extraction target (corrected from the
original two, and confirmed to exist and fetch successfully):
`content/files/applications/instructions_english_td.pdf`,
`content/files/applications/passport_application.pdf`, and
`content/files/applications/amendment.pdf`. The previously-scoped
`content/files/guidelines/Instructions for Online TD - Local
Applicants -english_3.pdf` is dropped from this change's target list.

**Under-16 content is ingested and chunked normally, not filtered out.**
These pages contain full under-16 passport requirements alongside adult
ones. This phase does not distinguish applicant age at all — that
distinction belongs to Phase 4 (rules engine), which will scope its v1 to
adult applicants only, ask age as a mandatory intake question, and return
an explicit "not yet covered" response for under-16 applicants (the
under-16 fee is Rs 3,000/9,000, not Rs 10,000/20,000 — returning an adult
checklist to a parent would be actively harmful). This change's job is
only to make sure that under-16 content is actually ingested and
retrievable so Phase 4 has something correct to scope around later —
verified directly in this change's own tasks, not assumed.

The site has no `robots.txt` (404) — no published crawl restrictions
beyond the rate-limiting this change already requires.

## What Changes

- Add a scraper (`api/app/scraper/`): httpx + BeautifulSoup fetches the
  five pages listed above, computes a SHA-256 content hash for each, and
  persists each as a `SourceDocument` (`document_type="html"`,
  `status="pending"`). Rate-limited and identifies itself with a
  descriptive User-Agent.
- Add PDF extraction (`api/app/ingestion/`): pdfplumber extracts text from
  the three instruction PDFs above, persisted the same way
  (`document_type="pdf"`).
- Add chunking (`api/app/ingestion/`): splits an ingested document's
  extracted text into ~200–400 word passages, each a `DocumentChunk` row
  with a foreign key to its `SourceDocument` — applied uniformly, with no
  content-based filtering (see the under-16 note above).
- Add embedding (`api/app/ingestion/`): sentence-transformers (CPU-only)
  embeds each chunk into `DocumentChunk.embedding` — the `vector(384)`
  column Phase 2 already created.
- Store the raw snapshot before any parsing, unmodified — parsing (PDF
  text extraction, chunking) is lossy; the snapshot is the audit trail
  BACKEND_PLAN.md and CLAUDE.md both require.

Explicitly out of scope: LLM rule parsing (BACKEND_PLAN.md 3.5), change
detection (3.6), any API route, and any citizen-facing use of this data —
scraped content stays `pending` until a human reviewer approves it
(CLAUDE.md: "Scraped content never goes live automatically").

## Capabilities

### New Capabilities
- `source-ingestion`: fetching a page or PDF from the Immigration
  Department site and persisting it as a hashed, timestamped,
  pending `SourceDocument` snapshot — before any parsing touches it.
- `document-chunking`: splitting an ingested document's extracted text
  into passages and embedding them locally into `DOCUMENT_CHUNK`,
  scoped to what this change actually builds (chunk + embed on demand,
  not the "re-embed on re-approval" lifecycle a later review-console
  change will add).

### Modified Capabilities
(none — `case-resolution-data-model` and `office-directory` from Phase 2
are read/written as-is, no schema change)

## Impact

- New code in `api/app/scraper/` and `api/app/ingestion/` (previously
  empty packages from Phase 1/2).
- No new Python dependencies — httpx, beautifulsoup4, pdfplumber,
  sentence-transformers, and pgvector are already pinned in
  `api/requirements.txt` from Phases 1–2.
- No schema change — writes to `source_document` and `document_chunk`,
  both created in Phase 2.
- No mobile app changes, no API routes, no LLM calls (rule parsing is out
  of scope for this change).
- Larger footprint than originally scoped: 8 `SourceDocument` rows (5
  html + 3 pdf) instead of 3, and their resulting chunks — not a
  different kind of change, just more of it.
- Network dependency: this change's scraper and PDF-extraction steps read
  from the live `immigration.gov.lk`, an external site this project does
  not control. Its content or availability can change between when this
  proposal is written and when it's implemented.
- `studio_e.php`'s studio listing appears to be populated dynamically
  (empty table in the static HTML fetch) — see design.md's Risks for how
  this change handles that.
