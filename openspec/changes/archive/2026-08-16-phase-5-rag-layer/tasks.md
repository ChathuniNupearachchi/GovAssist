## 1. Schema migration — SourceDocument.approved_at

- [x] 1.1 Add nullable `approved_at` (DateTime) to `SourceDocument` in
      `api/app/models.py`
- [x] 1.2 Generate and review the Alembic migration (check for the same
      class of autogenerate `None`-name FK bug seen in Phase 2 and
      Phase 4 before trusting it — this column has no FK, but check
      anyway) — clean this time, a plain nullable column, no FK-naming
      issue
- [x] 1.3 `alembic upgrade head`; verify the column exists — confirmed
      via inspector
- [x] 1.4 `alembic downgrade -1`; verify the column is gone and nothing
      else changed; re-apply — confirmed 16 tables (15 domain +
      alembic_version) after downgrade, column gone; re-applied cleanly

## 2. 5.0 — Strip navigation/footer boilerplate

- [x] 2.1 Update `api/app/ingestion/html_extraction.py` to decompose
      `<nav>`, `<section id="bottom">`, and `<footer>` before
      `.get_text()`
- [x] 2.2 Verify against all 5 HTML documents directly (not just one):
      confirmed exactly 212 words removed per page in every case
      (matches propose-time measurement exactly); spot-checked id=10
      still contains "1,200" and "Hour and 30" and studio_e.php's
      content (district selector + studio-list table headers) is real
      page content, not boilerplate
- [x] 2.3 Delete the existing `DocumentChunk` rows for the 5 HTML
      `SourceDocument`s (first-fetch rows) and re-run
      `chunk_and_embed_source_document` against the stripped text —
      id=7: 4→3 chunks, id=8: 5→5, id=9: 3→2, id=10: 2→1 (now one
      clean chunk instead of boilerplate-diluted), studio_e.php: 1→1
- [x] 2.4 Confirmed no resulting chunk consists mainly of
      navigation/footer text — inspected `chunk_text` directly for
      `id=10` and `studio_e.php`; neither contains "QUICK LINKS" or
      any nav/footer string

## 3. Document approval seed step

- [x] 3.1 Write `api/app/seed/phase5_approve_documents.py`: resolve the
      first-fetch `SourceDocument` for each of the 8 ingested URLs (5
      HTML + 3 PDF) by `source_url` ordered by `fetched_at` ascending
- [x] 3.2 Set `status="approved"`, `approved_at=now()` on each; leave
      the second-fetch HTML rows `pending`
- [x] 3.3 Verified: exactly 8 `SourceDocument` rows are `approved`
      (5 HTML + 3 PDF), the other 5 (HTML re-fetch rows) remain
      `pending`

## 4. Engine — retrieval + self-check (5.1, 5.3)

- [x] 4.1 `api/app/rag/retrieval.py`: `retrieve(db, query, top_k)` —
      embed the query with `all-MiniLM-L6-v2`, search `DOCUMENT_CHUNK`
      via `cosine_distance`, joined/filtered to `SOURCE_DOCUMENT.status
      = 'approved'` only
- [x] 4.2 Calibrated `WEAK_MATCH_THRESHOLD` against the real re-embedded
      corpus. Measured: "What is an authorised photo studio?" → 0.7152
      (correct doc, id=7); "What is the fee for a name change
      amendment?" → 0.5174 (correct doc, id=10); "What is the weather
      forecast for Paris tomorrow?" (absent topic) → 0.9681. Set
      threshold to 0.78. Also measured — and documented as a known
      limitation rather than hidden — that a genuinely in-corpus
      question phrased differently from the source ("What are the
      working hours at the Head Office?", covered by id=7) scored
      0.8311, above threshold; see design.md's Risks.
- [x] 4.3 Implemented the reformulation heuristic (strip question
      words/stopwords) and the retry-once flow: weak match -> reformulate
      -> retry -> still weak -> "no relevant match" result
- [x] 4.4 Unit tests: an approved-only scoping test — since no real
      pending document happened to have chunks, built a controlled
      pending document + chunk embedded to be the closest possible
      match, confirmed retrieval still excludes it, cleaned up after;
      a strong-match test; an absent-topic retry-then-no-match test

## 5. Engine — grounded generation (5.2)

- [x] 5.1 `api/app/rag/generation.py`: `generate_answer(chunks, query) ->
      RAGAnswer` — Claude API (`claude-opus-5`) call constrained to the
      retrieved chunks' content only, with each chunk's citation
      (reusing `app.engine.types.Citation`, populated from
      `SourceDocument.source_url` / `.approved_at`)
- [x] 5.2 "No relevant match" short-circuits before this module is
      called at all — `generate_answer` raises `ValueError` on an empty
      chunk list, and `answer.py`'s entry point never calls it when
      retrieval reports no relevant match
- [x] 5.3 Unit test: a generated answer's citations list is non-empty
      and each citation carries a `source_url` and non-null
      `verified_at` (populated from `approved_at`)

## 6. Engine — top-level answer entry point

- [x] 6.1 `api/app/rag/answer.py`: `answer_question(db, query) ->
      RAGResponse` ties retrieval, self-check/reformulation, and
      generation together; returns the explicit "I don't have that
      information" response when retrieval finds no relevant match
- [x] 6.2 Unit test: `RAGResponse`'s dataclass fields are exactly
      `{text, citations, grounded}` — structurally cannot carry a
      requirement set, fee, or office field — plus runtime checks for
      both the grounded and no-match paths

## 7. Done-When verification

- [x] 7.1 "What is an authorised photo studio?" → grounded answer citing
      `pages_e.php?id=7` — confirmed via `test_grounded_answer_returns_citations`
      and direct run (see below)
- [x] 7.2 "What is the fee for a name change amendment?" → answer citing
      `pages_e.php?id=10`, mentions LKR 1,200 — confirmed via
      `test_generated_answer_cites_every_passed_chunk` and direct run
- [x] 7.3 A question with no answer in the corpus → explicit "I don't
      have that information", not a fabricated answer — confirmed via
      `test_no_relevant_match_returns_explicit_response_no_generation_call`
- [x] 7.4 Confirmed via test (not just code review) that retrieval never
      returns a chunk from a non-approved document —
      `test_approved_only_scoping_excludes_pending_documents`
- [x] 7.5 Confirmed every returned answer's citations include source URL
      and `approved_at` (as `verified_at` on `Citation`)
- [x] 7.6 Re-ran the amendment-query ranking check from Phase 3
      (previously #6 of 25): after stripping boilerplate and
      re-chunking, `pages_e.php?id=10`'s single chunk is now the #1
      result (distance 0.5174) for "What is the fee for a name change
      amendment?" — confirmed directly via `_search`, not inferred
