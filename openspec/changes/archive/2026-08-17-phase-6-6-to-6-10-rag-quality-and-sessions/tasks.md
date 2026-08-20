## 1. Baseline measurement (before any implementation)

- [x] 1.1 Write a small calibration script that embeds each of the nine
      calibration queries and records the current system's cosine
      distance against the corpus (top match, current Phase 5 retrieval
      path, unmodified).
- [x] 1.2 Run it and record all nine cosine distances in `design.md`'s
      baseline table, confirming the three known values (0.5174, 0.8311,
      0.7358) match before trusting the other six.
- [x] 1.3 Commit the calibration script under `api/app/rag/` (or
      `api/scripts/`) so it can be re-run identically after every later
      phase — the same script measures 6.6, 6.7, and (if run) 6.8.

## 2. Phase 6.6 — Structure-aware chunking

- [x] 2.1 HTML: detect `<table>` elements before flattening to text;
      convert each to markdown preserving header row and cell structure.
      **Finding:** only `pages_e.php?id=10` uses a literal `<table>`;
      also detect `<ul>/<ol>` lists and `Label - Value` fee-line
      paragraphs as structured blocks — see design.md.
- [x] 2.2 HTML: splice each table's markdown back into the extracted
      text at its original position relative to surrounding prose.
- [x] 2.3 PDF: call `pdfplumber.extract_tables()` per page, independent
      of `extract_text()`; convert each table to markdown.
- [x] 2.4 PDF: merge extracted tables with extracted prose by page
      position, preserving reading order.
- [x] 2.5 Chunker: never split a table's markdown across chunks,
      regardless of word count; record any unusually large table
      encountered in the 8-document corpus in `design.md`. **Finding:**
      none — largest is id=10's 7x3 table.
- [x] 2.6 Alembic migration: add `DOCUMENT_CHUNK.metadata` JSONB column
      (nullable).
- [x] 2.7 Populate `document_title`, `section_heading` (nearest
      preceding heading), `content_type` (`prose`/`table`/`list`), and
      `source_url` on every chunk at chunk-build time.
- [x] 2.8 Build the embedded-text representation (context header +
      content) separately from the stored `chunk_text`; verify the
      header never appears in `chunk_text`.
- [x] 2.9 Re-chunk and re-embed all 8 approved documents with the
      existing `all-MiniLM-L6-v2` model.
- [x] 2.10 Verify the id=8 fee table and id=7 working-hours table are
      each a single structured chunk with markdown intact.
- [x] 2.11 Verify every chunk has non-null metadata.
- [x] 2.12 Re-run the calibration script; append the "After 6.6" column
      in `design.md`.
- [x] 2.13 Run Phase 5's existing RAG tests; confirm they still pass.
- [x] 2.14 Check for existing `PLAN_ITEM` rows referencing chunks being
      replaced (design.md's Open Question); note the finding in
      `design.md`. **Finding:** zero PLAN_ITEM rows exist — risk not
      live.

## 3. Phase 6.7 — Hybrid search

- [x] 3.1 Alembic migration: add a GIN-indexed `tsvector` expression (or
      generated column) over `DOCUMENT_CHUNK.chunk_text`.
- [x] 3.2 Implement full-text query via `plainto_tsquery` alongside the
      existing pgvector cosine query. **Finding:** `plainto_tsquery`
      alone under-recalls badly on identifier queries (AND-of-every-word
      semantics); added a narrow, digit-token-only OR "identifier
      rescue" list as a third ranked list — see design.md.
- [x] 3.3 Implement reciprocal rank fusion to blend the two (in the
      event, three) rankings into one score, keeping approval-only
      scoping in the same SQL join.
- [x] 3.4 Confirm the weak-match reformulation-retry flow operates on
      the blended score, unchanged in structure.
- [x] 3.5 Re-run the calibration script; append the "After 6.7" column
      in `design.md`.
- [x] 3.6 From the measured data, choose the accept/reject threshold;
      document the chosen value and the evidence in `design.md`.
      **Finding:** a single global fused-score cutoff could not
      separate the set (measured: several accept/reject queries tied at
      the same score) — built a two-tier rule instead (multi-signal
      agreement accepts outright; single-signal falls back to 6.6's
      calibrated cosine threshold, 0.55). Documented in full in
      design.md.
- [x] 3.7 Verify "working hours at the Head Office" retrieves
      `pages_e.php?id=7` as the top result.
- [x] 3.8 Verify "how do I renew my driving license?" returns no
      relevant match.
- [x] 3.9 Verify "Form K-35A" and "section 19(2)" both retrieve
      correctly (accept/reject correct for both; "section 19(2)"'s
      literal source chunk lands in the top-5 passed to generation, not
      top-1 — see design.md).
- [x] 3.10 Verify all nine calibration queries resolve correctly under
      the new threshold. **9/9 correct**, measured end to end via
      `retrieve()`.
- [x] 3.11 Run Phase 5's and 6.6's existing RAG tests; confirm they
      still pass. (`test_retrieval.py` updated for the new
      `.score`/`.vector_distance` fields — the metric itself is what
      6.7 changes; all 10 RAG tests plus the other 71 backend tests
      pass.)

## 4. Phase 6.8 — Embedding model upgrade (conditional gate)

- [x] 4.1 Check 1 — inspect the 6.7 calibration results: do all nine
      queries already resolve correctly with clear margin? Record the
      answer in `design.md`. **Result: yes** — 9/9 correct, measured
      end to end.
- [x] 4.2 If Check 1 says yes: record "assessed and found unnecessary"
      in `design.md` and stop — skip the remaining tasks in this
      section. **Done — STOP recorded in design.md; embedding model
      stays all-MiniLM-L6-v2.**
- [x] 4.3 Check 2 (only if Check 1 says no) — **not applicable; Check 1
      stopped first, so Check 2 was not run** (recorded in design.md,
      not silently skipped).
- [x] 4.4 (not applicable — see 4.3)
- [x] 4.5 (not applicable — no migration proceeds)
- [x] 4.6 (not applicable)
- [x] 4.7 (not applicable)
- [x] 4.8 (not applicable)
- [x] 4.9 (not applicable)
- [x] 4.10 (not applicable — "After 6.8" column in design.md's
      calibration table records "not run — Check 1 stopped" rather than
      being left blank)
- [x] 4.11 (not applicable)
- [x] 4.12 (not applicable — no change made, nothing to re-verify)
- [x] 4.13 (not applicable)

## 5. Phase 6.9 — Citation verification

- [x] 5.1 Define the structured generation schema (`answer: str`,
      `citations: list[{chunk_id: str, quoted_span: str}]`) and switch
      `api/app/rag/generation.py` to `client.messages.parse`.
- [x] 5.2 Implement the verification gate: every `citations[].chunk_id`
      SHALL be a member of the retrieved chunk id set passed to the
      model for that call.
- [x] 5.3 On a verification failure, retry generation once with an
      explicit "cite only the provided chunks" instruction.
- [x] 5.4 On a second verification failure, return the existing
      explicit "no relevant match" response.
- [x] 5.5 Treat an empty `citations` list as a verification failure,
      following the same retry-then-fallback path.
- [x] 5.6 Test: a mocked model response with a fabricated `chunk_id` not
      in the retrieved set is caught and rejected by the verification
      gate.
- [x] 5.7 Test: a mocked model response with an empty citation list is
      rejected.
- [x] 5.8 Test: the retry path is exercised — first response fails
      verification, second (retried) response passes.
- [x] 5.9 Run the real calibration queries end to end; confirm every
      resulting answer carries at least one verified citation. **All
      six accept queries: grounded=True with 1-4 real citations each,
      real Claude API calls, no mocking.**
- [x] 5.10 Run Phase 5's, 6.6's, and 6.7's existing RAG tests; confirm
      they still pass. (`test_generation.py`'s old
      "cites every passed chunk" test replaced with "cites from the
      retrieved set" — the old assertion encoded the pre-6.9 "cite
      everything unconditionally" behavior this phase deliberately
      supersedes. All 13 RAG tests plus the other 71 backend tests
      pass.)

## 6. Phase 6.10 — Persistent session memory

- [x] 6.1 Alembic migration: add `CHAT_MESSAGE` (`id`, `case_id` FK,
      `role`, `content`, `created_at`, `intent` nullable,
      `cited_chunk_ids` nullable JSONB).
- [x] 6.2 Persist every inbound and outbound chat message on
      `POST /chat/message`, including intent and cited chunk ids where
      applicable. (`generate_answer`/`RAGAnswer`/`RAGResponse` extended
      to carry the verified `cited_chunk_ids` list through from 6.9's
      gate, so the audit trail records real chunk ids, not just
      source-document citations.)
- [x] 6.3 Implement device-to-case resolution: given a device reference,
      find its most recent unresolved case, if any. (`app/chat/
      session.py::resolve_case_for_device` — ordered by the case's
      latest `CHAT_MESSAGE`, since Case itself has no `created_at`.)
- [x] 6.4 Wire device-to-case resolution into `POST /chat/message` so a
      returning device continues its case rather than starting a new
      one; confirm a device with no prior case still starts cleanly.
      Also: `POST /case/{id}/resolve` now sets `Case.resolved_at`,
      previously never set by anything — without it, a fully-resolved
      case would keep being "resumed" as if still in progress.
- [x] 6.5 Implement the Redis hot-session cache-aside layer (recent
      messages + answered facts, bounded TTL) around the case read path.
- [x] 6.6 Add a new endpoint returning the full, ordered message history
      for a device's active case. (`GET /chat/transcript?device_ref=`.)
- [x] 6.7 Test: a case interrupted mid-intake and resumed returns both
      the correct next question and the prior conversation.
- [x] 6.8 Test: closing and reopening (simulated by a fresh request with
      the same device reference) restores the visible transcript.
- [x] 6.9 Test: a device with no prior case starts cleanly, with no
      unrelated case attached.
- [x] 6.10 Test: clear Redis, then confirm the transcript still restores
      correctly from Postgres alone. All 5 new tests in
      `tests/api/test_session.py` pass (real API, real Postgres, real
      Redis); full 89-test suite passes.

## 7. Documentation and final calibration record

- [x] 7.1 Update `CLAUDE.md`'s RAG layer section to describe hybrid
      ranking and metadata-enriched chunks.
- [x] 7.2 Update `CLAUDE.md`'s Claude API jobs list if job #3
      (generation) or job #4 (OCR) descriptions no longer match actual
      behavior after 6.9. (Job #3 updated: structured output, verified
      citations. Job #4/OCR unaffected by this change.)
- [x] 7.3 Confirm `design.md`'s calibration table has one row per query
      and one column per phase actually executed (6.8's column reads
      "not run" — Check 1 stopped before Check 2, recorded not silently
      skipped).
- [x] 7.4 Final full-suite run: Phase 5 and Phase 6 existing tests, plus
      every test added in sections 2–6 above, all passing together.
      **89/89 passed** (`pytest tests -q`), real Postgres, real Redis,
      real Claude API calls throughout — no mocking except the four 6.9
      verification-gate tests, which mock only the model-response
      boundary by design.
