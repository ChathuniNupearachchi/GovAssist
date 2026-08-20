## 0. Precondition

- [x] 0.1 Confirm `phase-6-6-to-6-10-rag-quality-and-sessions` is
      archived (its 6.9 citation-verification and 6.10 `CHAT_MESSAGE`
      requirements must already be in `openspec/specs/` before this
      change's `MODIFIED` deltas apply cleanly). Archive it first if not.
      **Archived and synced to main specs.**
- [x] 0.2 Run the full existing suite (89 tests) and confirm a clean
      pass before making any change here, as the starting baseline.
      **89/89 pass.**

## 1. Data model: tool-call trace storage

- [x] 1.1 Add `ChatMessage.tool_trace` (JSONB, nullable) to
      `api/app/models.py`, matching `cited_chunk_ids`'s shape and
      docstring precedent.
- [x] 1.2 Alembic migration (autogenerate + review); apply it.

## 2. Tool wrappers (`api/app/chat/tools.py`)

- [x] 2.1 `retrieve_documents(db, query)` — wraps `app.rag.retrieval.
      retrieve`; returns a list of `{chunk_id, text, source_url,
      verified_at}` (no internal score/distance fields leaked to the
      model).
- [x] 2.2 `get_fee(db, service, urgency)` — wraps `app.engine.fees.
      resolve_fee` against the correct approved rule version for
      `service` (`"renewal"` | `"amendment"`); returns
      `{basis, base_amount, source_url, verified_at}` or a structured
      "no fee rule for this basis" result.
- [x] 2.3 `find_office(db, district, urgent)` — wraps `app.engine.
      offices.resolve_offices`; returns offices plus any conflict note,
      each with its citation.
- [x] 2.4 `get_next_question(db, case_id)` — wraps `app.engine.
      next_question.next_question`; read-only, does not record
      anything.
- [x] 2.5 `resolve_case(db, case_id)` — wraps `app.engine.resolver.
      resolve_case`; when intake isn't complete, returns a structured
      "not ready — still need: {prompt}" result instead of raising
      (same check `app/api/cases.py`'s route already makes).
- [x] 2.6 `compare_amendment_vs_renewal(db, case_id)` — computes both
      the renewal fee/requirements and the amendment fee/requirements
      unconditionally (not gated on `name_changed`), using the case's
      answers so far for basis/district; returns both sides plus
      citations. Verified live: both sides populate correctly even
      before intake is complete.
- [x] 2.7 JSON tool schemas (name, description, input schema) for all
      six, matching each wrapper's parameters.
- [x] 2.8 Malformed-argument handling: a tool call whose arguments don't
      satisfy its schema returns a structured tool-error result (not an
      unhandled exception) that the model can react to. Verified live:
      unknown service, missing argument, and unknown tool name all
      return structured errors, no exception raised.

## 3. Agent loop (`api/app/chat/agent.py`)

- [x] 3.1 Bounded tool-use loop over `claude-sonnet-5`
      (`client.messages.create(tools=[...])`): execute requested tool
      calls, append `tool_result` blocks, re-call the model, up to a
      fixed iteration cap (6); on cap exceeded, fall back to the
      explicit no-relevant-match response.
- [x] 3.2 Per-turn tool-call trace: record tool name, arguments, call
      order, and result for every call made, in the order made.
- [x] 3.3 Citation verification for `retrieve_documents` results:
      verify the final answer's chunk citations against the union of
      chunk ids returned by every `retrieve_documents` call that turn;
      reject-and-retry-once-then-fallback, reusing 6.9's mechanism.
- [x] 3.4 Structural verification for fee/office/requirement values:
      every such value in the composed answer must match a value
      actually returned by a `get_fee`/`find_office`/`resolve_case`/
      `compare_amendment_vs_renewal` call that turn (compare parsed
      values, not formatted text — see design.md's Risk note); same
      reject-and-retry-once-then-fallback shape.
- [x] 3.5 Wire `app/rag/answer.py` (or its caller in `app/chat/
      router.py`) to invoke the agent instead of the old single-shot
      `retrieve()` + `generate_answer()` path for open questions;
      `retrieve()`/`generate_answer()` themselves stay unchanged,
      `retrieve_documents` calls `retrieve()` directly.
- [x] 3.6 Persist the tool trace onto the assistant `ChatMessage` row
      for that turn (`tool_trace` column from section 1). **Findings
      during live testing** (all fixed, not just noted): (1) a 1024
      `max_tokens` cap truncated multi-step turns mid-`submit_answer` —
      raised to 4096 and truncation now triggers its own bounded retry;
      (2) `retrieve_documents`' default top_k (5) was too narrow once
      the agent verifies rather than blindly citing — widened to 8; (3)
      the model sometimes answered "I don't know" in plain text without
      trying a tool first — one bounded nudge-and-retry added, separate
      from the verification-failure retry budget; (4)
      `requirement_labels_used` was ambiguous between "an official case
      requirement" and "a document merely mentioned in retrieved text"
      — the schema/prompt now restricts it to the former, since the
      latter is already covered by `chunk_citations`.

## 4. Contextual question phrasing (`api/app/chat/rephrase.py`)

- [x] 4.1 `rephrase_question(canonical_prompt, attribute, recent_turns)`
      via `client.messages.parse` (`claude-haiku-4-5`), Pydantic
      `output_format` returning `{rephrased_text, target_attribute}`.
- [x] 4.2 Attribute-mismatch fallback: if `target_attribute` doesn't
      match the actual next-question attribute, return the canonical
      prompt.
- [x] 4.3 Failure fallback: any exception/timeout from the rephrasing
      call returns the canonical prompt, no error surfaced.
- [x] 4.4 Wire into `app/chat/router.py::handle_message` — rephrasing
      runs only after `next_question.py` has already selected the
      attribute; the canonical prompt (not the rephrased text) remains
      what's persisted as the case's pending-question reference and
      logged. (`QuestionOut.prompt` stays canonical; a new
      `display_text` field carries the rephrased text — additive, no
      existing consumer of `prompt` changed.)
- [x] 4.5 2,000-character truncation applies to any citizen text passed
      into the rephrasing prompt (recent turns); `max_tokens` cap set on
      the call.

## 5. Visible extraction acknowledgement (`api/app/chat/acknowledge.py`)

- [x] 5.1 `build_acknowledgement(recorded_facts, requirements_before,
      requirements_after)` — `requirements_before`/`requirements_after`
      from two real `app.engine.requirements.resolve_requirements`
      calls (with and without the newly recorded answer(s)); newly-
      triggered requirements are their set difference, not model-
      asserted.
- [x] 5.2 `claude-haiku-4-5` call turns the verified `(fact, value,
      [triggered requirement labels])` tuple into a sentence — wording
      only, no new facts introduced.
- [x] 5.3 No-recorded-fact case: a turn that records nothing produces no
      acknowledgement.
- [x] 5.4 Failure fallback: an acknowledgement-generation failure omits
      the acknowledgement (falls back to no acknowledgement, not an
      error) — the next question is still asked.
- [x] 5.5 Explicit guard: acknowledgement text never includes a fee
      amount or office name (structural check, not just prompt
      instruction). Implemented as data minimization (the model is never
      given a fee/office value at all, so it structurally cannot state
      one) plus a regex backstop that discards the acknowledgement if a
      currency pattern still appears.
- [x] 5.6 Wire into `app/chat/router.py::handle_message`, composed
      before the (possibly rephrased) next question in the same
      response.

## 6. Tests

- [x] 6.1 Test: "Should I amend my passport or get a new one?" produces
      a trace calling `get_fee` twice (renewal + amendment) and
      `retrieve_documents` at least once, and the response states both
      fees, both timelines, and citations.
      (`tests/chat/test_agent.py::test_amend_vs_renew_produces_a_multi_step_trace_with_both_fees`.)
- [x] 6.2 Test: that turn's tool trace is persisted and retrievable
      (queryable from `ChatMessage.tool_trace`).
      (`tests/api/test_conversation_polish.py::test_amend_vs_renew_tool_trace_is_persisted_and_retrievable` —
      accepts either the two-`get_fee`-calls path or the dedicated
      `compare_amendment_vs_renewal` tool, both of which the
      agentic-tool-answering spec's own scenario allows.)
- [x] 6.3 Test: no fee, office, or timeline value in any agent response
      across a small set of real queries fails to match a value actually
      returned by a tool call that turn (the structural verification
      itself, exercised end to end).
      (`tests/chat/test_agent.py`'s `test_verify_submission_*` tests.)
- [x] 6.4 Test: a mocked tool-selection call that fails (API error)
      falls back to the explicit no-relevant-match response, not a
      crash. (`test_api_failure_during_tool_selection_falls_back_to_none`.)
- [x] 6.5 Test: a mocked malformed tool-call argument is handled without
      an unhandled exception. (`tests/chat/test_tools.py` +
      `test_malformed_tool_call_from_the_model_does_not_crash`.)
- [x] 6.6 Test: "My passport expired last year" (with age the pending
      attribute) produces a contextually phrased question, and an answer
      to it still records against the `age` attribute.
      (`tests/api/test_conversation_polish.py::test_expired_passport_message_gets_a_contextual_age_question_and_records_correctly`.)
- [x] 6.7 Test: a mocked rephrasing whose `target_attribute` doesn't
      match the pending attribute falls back to the canonical prompt.
      (`tests/chat/test_rephrase.py`.)
- [x] 6.8 Test: a mocked rephrasing API failure falls back to the
      canonical prompt. (`tests/chat/test_rephrase.py`.)
- [x] 6.9 Test: "I got married and my name is different now" records
      `name_changed=true`, acknowledges the marriage certificate
      requirement (via the real engine diff), and the next question is
      not "has your name changed" again. **Finding:** the renewal
      service's marriage-certificate requirement is also gated on
      `dual_citizen != true` (see `app/engine/conditions.py`'s
      "a missing answer is always not-satisfied" rule), and
      `dual_citizen` is asked one question after `name_changed` in the
      real sequence — a name-change message sent alone can't show the
      requirement as newly triggered until `dual_citizen` is also known.
      The test states both facts in one message (the classifier extracts
      whatever a message states, not just the currently-pending
      attribute), which is both realistic and sufficient to exercise the
      real diff. Documented in the test and in
      `tests/chat/test_acknowledge.py`'s equivalent unit test.
- [x] 6.10 Test: an acknowledgement never contains a fee or office
      string, checked structurally across a small set of real
      extraction scenarios.
      (`tests/chat/test_acknowledge.py::test_acknowledgement_never_states_a_fee_even_if_the_model_tries`
      — mocks the model boundary to force a violation, confirming the
      regex backstop discards it; data minimization means this can't
      happen with the real model, so this proves the backstop itself.)
- [x] 6.11 Full regression: all 89 pre-existing tests still pass
      (2 updated for legitimate new behavior — see note below), plus
      every test added above. **110 total; 109 passed on the full run,
      1 real-API test failed once on model-selection variance and
      passed on immediate retry** — the same class of flakiness this
      project's existing real-API tests already accept (no mocking,
      "verify directly").

      **Two pre-existing tests updated, not left broken:**
      `tests/api/test_session.py::test_closing_and_reopening_restores_the_visible_transcript`
      and `::test_transcript_restores_after_redis_is_cleared` asserted
      the transcript contains *exactly* the citizen's own raw message
      text. 6.11.3 legitimately adds an acknowledgement message to the
      transcript when a turn triggers a new requirement (confirmed live:
      answering age=40 triggers the fingerprints prerequisite). Both
      tests now check that the citizen's own messages are present, in
      order — not that they're the transcript's only entries — which is
      what "closing and reopening restores the visible transcript" (the
      6.10 requirement these tests exist for) actually requires.

## 7. Documentation

- [x] 7.1 Update `CLAUDE.md`'s "How the Claude API is used" job list to
      describe the tool-using agent (open-question path) and the two
      presentation-only intake calls (rephrasing, acknowledgement).
- [x] 7.2 Update `CLAUDE.md`'s "Two kinds of question, two mechanisms"
      framing: situation→engine and question→agent still holds; note
      that the agent's tools include read-only engine calls, so "RAG
      supports the conversation; the engine produces the deliverable"
      still holds — the engine remains the only source of a plan, fee,
      office, or requirement value, reached now via tool calls in
      addition to direct route calls.
- [x] 7.3 Update `BACKEND_PLAN.md` to record Phase 6.11 alongside
      6.6–6.10, following that section's established format.
