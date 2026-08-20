## Context

Phase 5 built retrieval (cosine similarity over `all-MiniLM-L6-v2`
embeddings, scoped to approved documents) and grounded generation with a
weak-match reformulation retry (`rag-answering`). Phase 5's own
threshold calibration already showed the core problem this change
addresses: "working hours at the Head Office" (genuinely in the corpus)
scored 0.8311 cosine distance — *worse* than "how do I renew my driving
license" (not in the corpus) at 0.7358. No single cosine threshold can
separate the two. Investigating why led to the chunker itself: both
`pdfplumber.extract_text()` and BeautifulSoup's `get_text()` flatten
`<table>` and tabular PDF content into an undifferentiated word
sequence, which is exactly the shape of the corpus's two most
consequential documents (the fee schedule and the working-hours table).

See `proposal.md` — Why, for the fourth problem this change addresses
(unverified citations) and the fifth (conversation persistence), which
are independent of the retrieval-quality chain but sequenced after it
per the phase ordering below.

This design covers five ordered sub-phases — a baseline measurement,
then 6.6 through 6.10 — each of which must be measured before the next
begins, per `proposal.md`. Phases 6.6–6.9 are `rag-answering` /
`document-chunking` concerns; 6.10 is unrelated to retrieval and is
sequenced last because it depends on nothing built in 6.6–6.9.

## Goals / Non-Goals

**Goals:**
- Make the two highest-value documents in the corpus (fee schedule,
  working hours) retrievable as structured, citable content instead of
  flattened prose.
- Find a retrieval ranking and threshold that correctly separates all
  nine calibration queries, backed by measurement at every step.
- Only migrate the embedding model if 6.6+6.7 do not already resolve
  calibration and the target machine has headroom — never on assumption.
- Close the citation-fabrication gap: verify every citation Anthropic's
  model returns is a member of the retrieved set, not just trust it.
- Make a citizen's conversation durable across app restarts, using the
  device identity `case-api` already sends.

**Non-Goals:**
- No change to what produces a plan, fee, office, or checklist — the
  rules engine's exclusivity there is untouched (`CLAUDE.md` — "Two
  kinds of question, two mechanisms").
- No multilingual support (Sinhala/Tamil embeddings) — explicitly out of
  scope per `CLAUDE.md`; BGE-M3 is rejected for this phase on that basis
  alone, independent of its memory footprint.
- No LLM-driven conversation orchestration — router.py's flow stays a
  deterministic state machine, not delegated to an agent framework.
- No online payment, appointment booking, or citizen accounts — unaffected
  by this change.

## Decisions

### Baseline measurement comes first, and is a real task, not a placeholder
Before any code changes, Task 1 runs the nine-query calibration set
against the current (Phase 5) system and records actual cosine
distances. Three values are already known from Phase 5's own
calibration work and are reproduced here as the expected baseline;
the remaining six are measured fresh by Task 1 and filled in before 6.6
begins. **This design document does not fabricate those six values —
they are recorded when Task 1 runs, not guessed here.**

| Query | Expected | Corpus? | Baseline (cosine) | After 6.6 (cosine) | After 6.7 (fused / accept?) | After 6.8 (if run) |
|---|---|---|---|---|---|---|
| What is the fee for a name change amendment? | accept | in | 0.5174 (id=10) | 0.4675 (id=10) | 0.03132 (id=10) — ✅ accept | not run |
| What are the working hours at the Head Office? | accept | in | 0.8311 (id=7) | 0.5979 (id=7) | 0.03154 (id=7) — ✅ accept | not run |
| What is an authorised photo studio? | accept | in | 0.7152 (id=7) | 0.4029 (studio_e.php) | 0.01639, dist 0.4029 (studio_e.php) — ✅ accept | not run |
| What documents do I need for a dual citizen passport? | accept | in | 0.4700 (instructions_english_td.pdf) | 0.3781 (id=8) | 0.01639, dist 0.3781 (id=8) — ✅ accept | not run |
| What is Form K-35A? | accept | in | 0.6897 (id=9) | 0.5922 (id=7) | 0.10704 (id=9) — ✅ accept | not run |
| What happens under section 19(2)? | accept | in | 0.6622 (passport_application.pdf) | 0.6561 (passport_application.pdf) | 0.10653 (amendment.pdf) — ✅ accept | not run |
| How do I renew my driving license? | reject | absent | 0.7358 (id=8) | 0.7313 (id=10) | no relevant match — ✅ reject | not run |
| What is the weather in Colombo? | reject | absent | 0.7079 (studio_e.php) | 0.7402 (id=8) | no relevant match — ✅ reject | not run |
| How do I apply for a visa to Australia? | reject | absent | 0.5659 (id=8) | 0.5939 (id=8) | no relevant match — ✅ reject | not run |

**After 6.7, measured 2026-08-16** (`retrieve()` end to end, hybrid RRF
ranking — see "Hybrid ranking: three lists, not two" below): **all nine
calibration queries resolve correctly** — six accepted with the right
source document, three rejected outright. This is the first phase where
the full calibration set passes; 6.8's Check 1 (below) is answered by
this result directly.

**Threshold, and the evidence behind it.** Acceptance is a two-tier
rule, not a single global cutoff on the fused score:
1. **Multi-signal agreement** (fused RRF score above the single-signal
   floor of `1/61 ≈ 0.01639`, i.e. more than one ranked list placed the
   same chunk highly) accepts outright, regardless of raw cosine
   distance. This is what accepts "Form K-35A" (0.10704) and "section
   19(2)" (0.10653) — both fail Phase 5/6.6's cosine-only threshold on
   their own (distances 0.67 and 0.69, well above 6.6's ~0.55 accept
   range) but succeed because the identifier-rescue list (see below)
   independently agrees with the vector list.
2. **Single-signal fallback**: when only one list contributed (the
   common case for a plain-language query full-text can't help with —
   "photo studio", "dual citizen" both land exactly on the floor value),
   fall back to the raw cosine distance, thresholded at **0.55** — chosen
   from this table's own 6.6 measurements: accept-query distances
   cluster at 0.38–0.66, reject-query distances at 0.59–0.74, and 0.55
   is the value that clears every accept query with margin while still
   rejecting "visa to Australia" (0.5939), the closest false-accept
   risk in the set.

A single global fused-score cutoff was tried first and rejected by
measurement, not intuition: with a uniform RRF blend, reject queries and
several accept queries landed on the *identical* floor value (many
queries' top vector match doesn't overlap with any full-text hit at
all), making them indistinguishable by score alone — see "RRF's
single-signal floor problem" below for the full record of what was
tried and why it didn't separate the set.

**After 6.6, measured 2026-08-16** (`python -m app.rag.calibration`, top-1
cosine distance, table/list-aware chunking + metadata context headers,
`all-MiniLM-L6-v2` unchanged): the worst-scoring in-corpus query, working
hours, improved from 0.8311 to 0.5979 — the single biggest move in the
table, confirming the table-flattening theory directly. "Authorised
photo studio" now correctly top-matches `studio_e.php` itself (was
`pages_e.php?id=7` at baseline) — the context header's `Document:
Authorised Photo Studios` line is doing real disambiguating work.
Accept-query distances now range 0.378–0.656; reject-query distances
range 0.594–0.740 — real separation opened up, but still overlapping
(the "visa to Australia" reject query at 0.5939 still scores below three
accept queries), so **no single cosine threshold yet separates all nine
correctly** — 6.7 remains necessary, not optional, exactly as planned.

Measured 2026-08-16 with `python -m app.rag.calibration` (Task 1) against
the unmodified Phase 5 system, top-1 cosine distance via `_search`,
before any of this change's code exists. All three previously-known
values (0.5174, 0.8311, 0.7358) matched exactly, confirming the harness
reproduces Phase 5's own calibration. The two other "reject" queries
score even lower than the driving-license case (0.5659 and 0.7079) —
both well inside what a naive "accept below ~0.75" threshold would
accept, underscoring 6.7's premise directly: no single cosine cutoff
separates accept from reject across this set, in either direction.

Each phase's task list ends with "recalibrate and append the column
above" — the table is a living artifact updated in place through
implementation, not rewritten per phase.

### 6.6 precedes 6.7 (chunking before ranking)
Retuning a ranking function over badly-chunked content measures the
wrong thing: if the fee table is still an undifferentiated number
sequence, no ranking algorithm can make "which fee applies to an urgent
application" resolve correctly, because the information isn't
represented in a way that's separable. Chunking is fixed first so
ranking is tuned against the corpus's real structure.

### Table extraction: markdown, spliced in place, one chunk regardless of size
HTML: parse before flattening to text, detect `<table>`, convert each to
markdown (`|`-delimited rows, header row preserved), and splice the
markdown back into the document's text stream at the table's original
position — so a table appears in reading order relative to the prose
around it, not appended or reordered.

PDF: `pdfplumber.extract_tables()` is called independently of
`extract_text()`; page text and page tables are extracted separately,
then merged by position on the page.

A table's markdown is never split across chunks, even when it exceeds
the ~200–400 word prose target — the whole point is that a citizen
asking about the urgent fee gets the whole fee table, not a fragment
missing the column headers that disambiguate normal/urgent/under-16. If
a table this corpus contains turns out to be large enough that "keep it
whole" produces an unusually large chunk, that specific exception is
recorded here during implementation (Task in 6.6), not decided
speculatively now — the 8-document corpus is small enough to check by
hand.

**Implementation finding, recorded after building this (6.6 Task 2.5):**
no table or list block in this corpus turned out large enough to be an
exception — the biggest is `pages_e.php?id=10`'s alterations table at 7
rows / 3 columns, comfortably inside a single chunk. No oversized-table
handling was needed.

**Implementation finding: the corpus's structured content is mostly not
literal `<table>` markup.** Direct inspection of all 5 approved HTML
snapshots (done before writing extraction code, not assumed) found real
`<table>` elements in exactly one document — `pages_e.php?id=10`'s
alterations fee table. The two documents this phase specifically
targets, `pages_e.php?id=7` (working hours) and `pages_e.php?id=8` (fee
schedule), mark that content up as `<p>Label - Value<br>Label -
Value</p>` pairs (fee lines) and `<ul>/<li>` lists under a bold-question
paragraph (office hours) — CMS-authored content, not semantic table
markup. Detecting only literal `<table>` tags would have left both of
this phase's headline DONE WHEN targets unfixed. Extraction therefore
detects three structural shapes, not one: real `<table>` elements,
`<ul>/<ol>` lists, and paragraphs whose lines are `Label - Value` pairs
— each becomes its own table/list block, tagged `content_type` `table`
or `list` accordingly. This satisfies the requirement's intent (tabular/
list-shaped content becomes a structured, atomic, disambiguated chunk)
using the mechanism the actual corpus requires, not the one a generic
"HTML tables" description assumed. See
`api/app/ingestion/html_extraction.py`'s module docstring for the same
note in the code.

**Implementation finding: PDF table interleaving is page-level, not
pixel-level.** `pdfplumber.extract_tables()` found exactly one real
table in the corpus's two text-layer PDFs (an office-use "Controller's
Order Minute Sheet" on page 2 of `passport_application.pdf`, not
citizen-relevant content) and none in the third (scanned, Claude-OCR
extracted, where no native table detection is available at all — that
document's blocks stay prose-only, split on blank lines as before).
Extraction appends each page's table block(s) after that page's prose
block, in page order — exact document order at the page granularity
this corpus needs, not exact pixel-position interleaving within a page,
which would need bounding-box comparison the corpus's one real PDF table
doesn't justify building.

### Metadata header: embedded text only, never the stored/cited text
The context header (`Document: / Section: / Source:`) is prepended only
to the string passed to the embedding model. `chunk_text` (what a
citation displays to a citizen) stores raw content. This keeps citations
clean while giving the embedding model disambiguating context it
currently lacks — a chunk of table rows with no surrounding text is
otherwise nearly meaningless to a sentence embedding model.

### Hybrid ranking: reciprocal rank fusion over pgvector cosine + Postgres full-text
RRF needs no tuned weight between the two signals — each result's score
is `1/(k + rank)` in one ranking system plus `1/(k + rank)` in the
other, summed. This matters here specifically because vector and
full-text search fail on *opposite* query shapes (semantic paraphrase vs.
exact identifier), so a weighted blend would need per-query-type tuning
this project has no data to justify; RRF sidesteps that by rewarding
whichever signal ranks a candidate highly, from either source.

**Implementation finding: hybrid ranking ended up three lists, not two,
and `plainto_tsquery` alone doesn't work for this corpus.** Building
this against the real corpus surfaced two problems the plan didn't
anticipate, both confirmed by direct measurement, not assumed:

1. **`plainto_tsquery`'s implicit AND-of-every-word is too strict for a
   natural-language question.** `plainto_tsquery('english', 'What
   happens under section 19(2)?')` requires the literal word "happens"
   to appear in a chunk — it never will, even in the one chunk that
   genuinely discusses "section 19(2)". Confirmed directly: this query
   returned zero full-text matches, even though the identifier it's
   asking about is in the corpus verbatim. AND semantics do have a real
   upside, though — measured zero false-positive full-text matches
   across all three reject queries, which is exactly the property that
   makes it safe to keep as the default.
2. **A single fused RRF score, with a uniform blend of two lists, could
   not separate the calibration set at all.** Most queries' top vector
   match has *no* corresponding full-text hit in the same chunk — full-
   text legitimately found nothing (case 1 above), or found a different
   chunk than the one vector search preferred. That leaves the query's
   fused score sitting at the "single-list, rank 0" floor value,
   `1/(k+1)`, identical for a strong accept query (e.g. "authorised
   photo studio", vector distance 0.40) and a genuine reject query
   ("driving license") whose nearest chunk — however irrelevant — is
   still vector rank 0. Measured directly: several accept and reject
   queries landed on the exact same fused score, making a single global
   cutoff on that score impossible, the same failure mode this phase
   exists to fix, just moved into the new metric instead of solved.

**The fix, in the code, not just documentation:** three ranked lists,
not two, and a two-tier accept rule instead of one global cutoff —
see `api/app/rag/retrieval.py`'s module docstring and the calibration
table's "Threshold, and the evidence behind it" note above for the full
mechanism and the measurements behind each choice:
- **Vector** (pgvector cosine, unchanged from 6.6).
- **Full-text, AND semantics** (`plainto_tsquery` as originally
  planned) — kept because it has zero measured false positives on this
  corpus, even though it under-recalls on exact identifiers.
- **Identifier rescue, OR semantics, narrow scope**: built only from a
  query's digit-bearing tokens (and their split letter/digit runs, so
  "K-35A" also tries "K" | "35" | "A" — the corpus spells the same form
  "K 35 A", space-separated, which tokenizes as three separate lexemes
  no merged-compound query term would ever match). Empty for any query
  with no digit-bearing token at all, which is every reject query in
  this calibration set — this is what keeps the rescue list from
  reintroducing false positives the way an unrestricted OR-of-all-
  keywords did when tried first (measured: an unrestricted OR-of-
  keywords rescue made "weather in Colombo" score in the same range as
  genuine accept queries, because "Colombo" alone is common enough in
  the corpus to look relevant on its own). Weighted with a smaller RRF
  `k` (10, vs. 60 for the other two lists) — this list is small and
  high-precision by construction, so a good rank in it is worth more
  than the same rank in a whole-corpus list; still no per-query-type
  tuning, since the same `k` applies to every query and the list
  contributes nothing at all to the large majority that have no
  digit-bearing token.
- **Accept rule**: agreement between ≥2 lists (fused score above the
  single-signal floor) accepts outright; a single-signal result falls
  back to the calibrated raw cosine distance (0.55). This is still "no
  tuned weight between vector and full-text" in the sense the plan
  meant — there's no coefficient trading one signal's importance against
  the other's; the fallback is Phase 6.6's own already-measured cosine
  threshold, used only when RRF genuinely has nothing else to go on.

**Alternatives considered** (from the request, recorded per the global
constraint to document rejected alternatives):
- **Qdrant / Pinecone with native BM25 sparse vectors** — rejected.
  Postgres `ts_rank` is TF-IDF-like without BM25's document-length
  normalization, but at this corpus size (8 documents, ~100–200 chunks)
  normalization has negligible effect, and a separate vector store would
  break the single SQL join that currently enforces approval-only
  scoping in the database rather than in application code — moving that
  check into app code is a bigger risk than the ranking gap. If hybrid
  search still underperforms after 6.7, the recorded upgrade path is the
  `pg_search` extension for true BM25, staying inside Postgres.

### 6.8 is conditional, and this proposal does not pre-commit its outcome
The proposal's Modified Capabilities deliberately excludes a
`document-chunking` embedding-dimension change. Two independent checks
gate whether 6.8 happens at all:
1. **Necessity** — only proceed if 6.6+6.7 leave calibration queries
   unresolved with clear margin. If they already resolve all nine, 6.8
   is skipped and that assessment is recorded here.
2. **Memory headroom** — measure available RAM with the full dev stack
   running (Docker, VS Code, dev server) on the target ASUS VivoBook
   (i3-1115G4, 2 cores, 20GB installed). Below 6GB available, stop;
   `bge-base-en-v1.5` needs ~1.5–2GB resident and this machine has no
   CUDA-capable GPU to offload to.

Because the outcome is unknown until both checks run during
implementation, **no spec delta for the embedding-dimension change is
included in this change's `specs/`.** If 6.8 proceeds, its task
explicitly includes writing a follow-up delta to
`case-resolution-data-model` (and `document-chunking`'s embedding
dimension requirement) before the migration is considered done — spec
and implementation stay in lockstep rather than the spec silently
lagging a schema change. This avoids inventing a requirement that may
never happen, per this workflow's own constraint against fabricating
requirements to satisfy validation.

**Check 1 result, measured 2026-08-16: STOP — not needed.** All nine
calibration queries resolve correctly after 6.6+6.7 (see the calibration
table's "After 6.7" column) — six accepted with the right source
document, three rejected outright, measured end to end through
`retrieve()`, not just top-1 score inspection. Margin is real though not
enormous on the tightest case: the single-signal cosine fallback
threshold (0.55) sits 0.044 below the closest reject query ("visa to
Australia", 0.5939) and clears every accept query in that tier by at
least 0.10 (worst case "authorised photo studio" at 0.4029 — actually a
much wider margin, 0.147, once distance is read the right direction);
the multi-signal-agreement tier ("Form K-35A", "section 19(2)") clears
the accept/reject boundary by roughly 6x (fused scores ~0.107 vs. the
~0.016 floor every reject query sits at). **Check 2 (available RAM) was
not run** — Check 1's own STOP condition means it doesn't need to be;
running it anyway would have been measuring something the decision
didn't depend on. The embedding model stays `all-MiniLM-L6-v2`. This
assessment can be revisited if a future calibration query class this
set doesn't cover turns out to need it.

**Alternatives considered:**
- **BGE-M3** (1024 dims, 2.2GB) — rejected: multilingual capability is
  moot (English-only build) and 2.2GB resident is not viable on this
  machine's typical ~4GB available headroom.
- **text-embedding-3-small (OpenAI API)** — rejected: introduces a
  second external LLM provider, per-call cost at both ingestion and
  query time, and sends every citizen query to a third party — breaking
  the local/no-GPU/no-per-query-cost property `CLAUDE.md` establishes
  for the RAG layer.

### Citation verification is a set-membership check, not a second model call
After `client.messages.parse` returns structured `{answer, citations}`,
every `citations[].chunk_id` is checked against the set of chunk ids
actually passed to the model in that call — an in-process set
comparison, zero additional runtime cost or latency. Failure triggers
exactly one retry with an explicit "cite only the provided chunks"
instruction; a second failure returns the same "no relevant match"
response Phase 5 already uses for weak retrieval, so citizens see one
consistent failure mode rather than two different ones.

An empty citation list is treated identically to a fabricated citation
— both mean "this isn't a real grounded answer" — because CLAUDE.md's
content rule ("never state a fee, document, or deadline without a
verified source") applies to a well-formed but citation-less answer just
as much as to an outright fabrication.

### Persistent session memory: Postgres is truth, Redis is a cache, never the reverse
`CHAT_MESSAGE` in Postgres is written on every turn and is the only
place a "clearing the cache still restores the transcript" scenario can
be verified against. Redis holds a bounded-TTL hot copy of the active
case's recent messages and answered facts purely as a fast path for the
common case (an in-progress conversation) — it is never read as the
system of record, and losing it never loses data, only round-trip
latency on the next read.

Device identity reuses the UUID `case-api` (Phase 6) already sends per
request; this change adds the *resolution* logic (device → most recent
unresolved case) and the transcript endpoint, not the identity mechanism
itself.

**Alternative considered:** LangGraph for multi-turn orchestration —
rejected. GovAssist's flow is derived deterministically from
`CONDITION` rows in the database; that determinism is what makes the
system defensible — the same case always produces the same plan and the
same question sequence. Handing question selection to an LLM agent would
make identical situations produce different (or occasionally skipped)
questions and would create a second source of truth alongside
`CASE_ANSWER`. The underlying maintainability concern is addressed
separately by formalizing `router.py` as an explicit typed state machine
(`AWAITING_ANSWER`, `ANSWERING_QUESTION`, `READY_TO_RESOLVE`,
`SCOPE_GATED`) with documented transitions — not by adopting a framework
built around non-deterministic flow control.

**Alternative considered (ingestion, not session-related):** PyMuPDF
alongside pdfplumber — rejected. PyMuPDF is faster on flowing text;
pdfplumber is better on tables. With three PDFs in the corpus, extraction
speed is irrelevant, and the actual defect was calling `extract_text()`
on tabular content, not the library — which 6.6 fixes directly. A second
PDF dependency for no measured gain is dependency creep this project
doesn't need.

## Risks / Trade-offs

- **[Risk]** Re-chunking and re-embedding all 8 documents in 6.6
  invalidates existing `PLAN_ITEM` → `DOCUMENT_CHUNK` references used
  for citations on already-saved plans. → **Mitigation:** chunk
  identity is not guaranteed stable across a re-chunk; this is the same
  "affected saved plans get flagged" concern Phase 9's approve/publish
  flow already exists to handle. Record in the 6.6 task whether any
  saved plans exist yet in this environment (likely none, pre-Phase 7)
  before treating this as live risk.
- **[Risk]** RRF's fixed-`k` behavior can still under-rank a genuinely
  relevant chunk if both signals rank it moderately (neither top-1 in
  either system). → **Mitigation:** the 9-query calibration set is
  exactly the check for this; 6.7 is not "done" until all nine resolve
  correctly, not just the two motivating examples.
- **[Risk]** The verification-gate retry doubles generation latency on
  the (hopefully rare) failure path. → **Mitigation:** acceptable
  because it only fires on a citation defect, and the alternative
  (serving an unverified answer) is the exact failure this architecture
  exists to prevent; a slow correct answer beats a fast wrong one here.
- **[Risk]** Redis TTL expiring mid-conversation on a slow citizen could
  make a *resumed-within-TTL* case pay a Postgres round-trip it wouldn't
  otherwise. → **Mitigation:** this is a latency detail, not a
  correctness one — Postgres remains authoritative regardless of TTL
  state, per the "Persistent session memory" decision above.
- **[Trade-off]** Skipping 6.8 (if the checks say to) leaves retrieval on
  a smaller, weaker embedding model long-term. → Accepted: the
  conditional gate exists specifically so this trade-off is made on
  measured evidence (calibration results, available RAM) rather than
  assumed necessary.

## Migration Plan

1. Baseline measurement (Task 1) — no code change, no rollback needed.
2. 6.6 — Alembic migration adds `DOCUMENT_CHUNK.metadata` (JSONB,
   nullable during backfill, then populated by re-chunking). Re-chunk
   and re-embed all 8 approved documents; existing chunk rows are
   replaced, not appended, so retrieval never sees stale and rebuilt
   chunks for the same document simultaneously. Rollback: revert the
   migration and re-run the prior chunker if the re-chunk output fails
   validation before it's used in retrieval.
3. 6.7 — Alembic migration adds the `tsvector` GIN index. Purely
   additive; rollback drops the index and index-maintenance trigger with
   no data loss, and retrieval falls back to cosine-only ranking.
4. 6.8 (conditional) — if it proceeds: `vector(384)` → `vector(768)`
   requires re-embedding every chunk before the column type change is
   usable; do this via a new column (`embedding_v2`), backfill, then
   swap, so retrieval never has a window where some rows are 384-dim and
   others 768-dim under the same query path. Rollback: keep the old
   column until the new one is verified against the calibration set.
5. 6.9 — code-only change to `api/app/rag/generation.py`; no schema
   change, no migration. Rollback is a code revert.
6. 6.10 — Alembic migration adds `CHAT_MESSAGE`. Additive; rollback
   drops the table. Redis usage is opt-in cache-aside and requires no
   migration; if Redis is unavailable, the design's "Postgres is truth"
   decision means the system degrades to reading Postgres directly
   rather than failing.

## Open Questions

None remaining. The one open question this document carried during
planning — whether any `PLAN_ITEM` rows already existed in this
environment that referenced chunks being replaced in 6.6 — was checked
directly during implementation: zero exist, so the citation re-linking
risk above was theoretical here, not live. See the Risks section and
`tasks.md` 2.14 for the record.
