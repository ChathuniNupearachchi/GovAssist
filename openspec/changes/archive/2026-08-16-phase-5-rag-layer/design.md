## Context

See proposal.md for motivation. Two decisions were resolved with the
user before writing specs:

1. **Document approval**: nothing has ever been approved (no admin
   console exists — Phase 9 is future work), so a seed/fixture step
   approves the 8 first-fetch `SourceDocument` rows, mirroring Phase 4's
   rule-version approval precedent. Without this, retrieval (scoped
   strictly to approved documents) has nothing to return.
2. **Self-check design**: a pure cosine-similarity threshold, no extra
   Claude API call for judging match quality or reformulating the query
   — stays within CLAUDE.md's four authorized narrow Claude API jobs
   rather than adding a fifth.

Boilerplate measurement (done directly against the actual snapshots
before writing this document, not assumed): every one of the 5 HTML
documents carries an identical 128-word `<nav>` menu and an identical
84-word `<section id="bottom">` block (quick links / related links /
join us / contact us) — 212 words removed per page in every case,
verified by measuring all 5 pages, not just one. The existing `<footer>`
tag (28 words: copyright line + "Last Update" date + visitor counter)
is stripped too — its date changes on every fetch, which would churn
chunk text and hashes without adding citizen-relevant content, and it
carries no rule content either. On `pages_e.php?id=10` (the shortest
page, 484 words total), stripping brings it to 272 words — previously
the boilerplate filled most of its first chunk; now the page's real
content (the amendment fee table) stands alone as clean content.

## Goals / Non-Goals

**Goals:**
- Boilerplate no longer dilutes any HTML chunk's embedding.
- Retrieval never returns unapproved content.
- A generated answer is always grounded and cited, or explicitly absent
  — never guessed.
- Citations on RAG answers and checklist items share one format.

**Non-Goals:**
- No API routes, no chat intake, no intent classification (situation vs.
  open question) — that's Phase 6.
- No admin review console (Phase 9) — approval here is a seed/fixture
  step, explicitly not a substitute for real review workflow.
- No caching (Phase 8).
- Query reformulation is a simple heuristic, not an LLM rewrite — see
  Context's self-check decision.

## Decisions

### Boilerplate stripping selectors
`html_extraction.py` decomposes `<nav>`, `<section id="bottom">`, and
`<footer>` (in that order, before calling `.get_text()`) rather than
diffing a known boilerplate string against page text. Alternative
considered: string-diff the identical boilerplate text out. Rejected —
the tag-based approach is exact (no partial-match edge cases), doesn't
break if whitespace/formatting shifts between fetches, and the
`<nav>`/`<section id="bottom">`/`<footer>` structure was confirmed
identical across all 5 pages by direct inspection of the raw HTML.

### `SourceDocument.approved_at`, not a reused `verified_at` name
Named `approved_at` rather than `verified_at` (which `RuleVersion`
already uses) because the two record different things: `RuleVersion.
verified_at` is when a human verified the *rule content* against the
source; `SourceDocument.approved_at` is when the *document itself* was
approved for retrieval. Reusing the same field name across two
different tables recording two different events would be more
confusing than two clearly-named columns. Citations still surface a
single "verified as of" date to the citizen — RAG answers use
`SourceDocument.approved_at`, checklist items use `RuleVersion.
verified_at` (via `app.engine.types.Citation`, reused as-is by the RAG
module for exactly this reason: same shape, `source_document_id` +
`source_url` + `verified_at`, so a citation looks identical to a citizen
regardless of which path produced it).

### Similarity threshold and reformulation
Retrieval uses pgvector's cosine distance (`DocumentChunk.embedding.
cosine_distance(query_vector)` — lower is more similar). A fixed
threshold decides "weak": the exact value is calibrated during
implementation against the actual re-embedded corpus (task 5.1 in
tasks.md) rather than guessed here, since the real distribution of
distances depends on the now-cleaner chunk embeddings. Reformulation
strips a fixed list of English question words/stopwords ("what", "is",
"the", "a", "an", "how", "do", "i", "can", "where", "does", etc.) from
the query and retries with the remaining keywords — cheap, deterministic,
no LLM call.

### Approval seed step
A new script (`api/app/seed/phase5_approve_documents.py`) resolves each
of the 8 ingested URLs' first-fetch `SourceDocument` (by `source_url`
ordered by `fetched_at` ascending — the same stability convention Phase
4 established) and sets `status="approved"`, `approved_at=now()`. The
second-fetch row for each of the 5 HTML URLs (Phase 3's re-scrape,
differing only by a live visitor counter) is left `pending` and is never
approved — approving it too would let retrieval return duplicate chunks
for the same content.

### Re-chunking is destructive and idempotent
Re-chunking the 5 HTML documents deletes their existing `DocumentChunk`
rows before inserting freshly stripped-and-embedded ones (same session,
so no window where a document has zero chunks visible to a concurrent
reader in production — though there are no concurrent readers in this
dev-only phase). PDFs are untouched entirely — no boilerplate there.

## Risks / Trade-offs

- [Risk] A fixed cosine-distance threshold tuned once against this small
  8-document corpus may not generalize as more documents/departments are
  added later. → Mitigation: threshold is a single named constant
  (`WEAK_MATCH_THRESHOLD`) in `retrieval.py`, not scattered, and the
  Done-When verification task records the actual measured distances for
  the two named test queries so a future tuning pass has a baseline to
  compare against.
- [Risk] **Confirmed during calibration, not hypothetical**: the
  threshold that correctly accepts both required Done-When queries
  (0.7152, 0.5174) and correctly rejects a clearly absent topic (0.9681
  for a weather question) also rejects a genuinely in-corpus, answerable
  question phrased differently from the source text — "What are the
  working hours at the Head Office?" (covered by `pages_e.php?id=7`)
  measured 0.8311, above the 0.78 threshold. A looser threshold fixes
  that false negative but starts accepting topically-adjacent-but-
  uncovered queries instead (e.g. "How do I renew my driving license?"
  measured 0.7358). → No mitigation beyond documenting it: this is a
  real limitation of a small corpus + a general-purpose sentence
  embedding model, not a bug in the threshold logic. `all-MiniLM-L6-v2`
  was chosen in Phase 3 for being CPU-only and free, not for retrieval
  precision — a better model or a corpus-specific fine-tune is the real
  fix, and is out of scope for this phase.
- [Risk] Stripping by tag name (`<nav>`, `<section id="bottom">`,
  `<footer>`) is coupled to this specific site's current template; a
  site redesign would silently stop stripping boilerplate rather than
  erroring. → Mitigation: the "no chunk consists mainly of navigation
  links" scenario in document-chunking's spec is checked as an explicit
  task against the real re-chunked output, so a template change that
  breaks stripping would be caught the next time chunking is exercised,
  not silently trusted.
- [Risk] The keyword-stripping reformulation is weak compared to what an
  LLM rewrite could do, so some genuinely-answerable questions may still
  fall through to "no relevant match." → Accepted per the user's
  decision (Context) — this stays within CLAUDE.md's four authorized
  Claude API jobs; a fifth job can be proposed later if this proves to
  be a real gap in practice.

## Migration Plan

One Alembic migration: add nullable `approved_at` (DateTime) to
`source_document`. Reversible — downgrade drops the column, leaving the
other 15 Phase 4 tables/columns untouched.
