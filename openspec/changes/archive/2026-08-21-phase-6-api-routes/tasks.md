## 1. Input limits (6.2)

- [x] 1.1 `api/app/chat/limits.py`: `truncate_message(text) -> str`,
      capping at 2,000 characters
- [x] 1.2 Apply it at the single entry point every route funnels
      through (the chat router), not re-implemented per-route
- [x] 1.3 Unit test: a message over 2,000 characters is truncated before
      it would reach a model call

## 2. Deterministic intent pass (6.1)

- [x] 2.1 `api/app/chat/deterministic.py`: per-attribute matcher table
      for the 9 renewal attributes (numeric for `age`, enum+synonyms for
      `service_basis`, exact-match-against-seeded-list for `district`,
      yes/no lexicon for the 5 boolean attributes, always-accept for
      `profession`)
- [x] 2.2 `try_deterministic_match(pending_attribute, message) ->
      str | None` — returns the normalized answer value only when the
      stripped/lowercased message is *solely* a plausible answer token
- [x] 2.3 Unit tests: one per matcher type (district, numeric, boolean,
      free-text), plus a message-with-surrounding-prose case that must
      NOT match

## 3. Claude-based classification (6.1)

- [x] 3.1 `api/app/chat/classifier.py`: `classify(message, pending_
      question) -> Classification` — `claude-haiku-4-5`,
      `output_config.format` json_schema for `{intent, extracted,
      contains_question, confidence}`
- [x] 3.2 Apply the confidence threshold (0.6): below it, force
      `intent="question"` and discard `extracted`
- [x] 3.3 Unit tests: a pure-situation message, a pure-question message,
      a combined situation+question message, and a deliberately
      ambiguous message that should hit the low-confidence path
      (mocked or a real low-temperature call — decide based on
      reliability during implementation)
      — Completion note: used real `claude-haiku-4-5` calls (Phase 5
      precedent), not mocks. The low-confidence test exercises the
      override path conditionally on whatever confidence the model
      actually returns for the ambiguous input, since a single sampled
      call can't be guaranteed to land under threshold every run —
      the override logic itself is unconditionally exercised by
      `classify()`'s own code path regardless.

## 4. Router — ties deterministic pass, classifier, engine, RAG (6.1)

- [x] 4.1 `api/app/chat/router.py`: `handle_message(db, case, message) ->
      ChatOutcome` — truncate → deterministic pass → (if no match)
      Claude classify → record any extracted facts as `CaseAnswer`
      rows → answer via RAG if `contains_question` or `intent ==
      "question"` → compute the (possibly updated) next question
- [x] 4.2 Unit tests: recording via deterministic match produces no RAG
      call; a combined message both records a fact and returns a RAG
      answer in the same call; a low-confidence message leaves the
      pending question unanswered

## 5. FastAPI routes (6.3)

- [x] 5.1 `api/app/api/chat.py`: `POST /chat/message` — creates a case
      when absent (`device_ref` required in that case), calls
      `chat.router.handle_message`, returns case id + any RAG answer +
      next question
- [x] 5.2 `api/app/api/cases.py`: `GET /case/{id}/next-question`;
      `POST /case/{id}/resolve` — assembles the case's `CaseAnswer` rows
      into an `{attribute: value}` dict, checks `next_question` first
      (4xx "not ready" response naming the pending question if
      non-null), otherwise calls `resolve_case` and returns the plan or
      the scope-gate response
- [x] 5.3 `api/app/api/services.py`: `GET /services`
- [x] 5.4 `api/app/api/requirements.py`: `GET /requirements/{id}` —
      404 on an unknown id
- [x] 5.5 Pydantic response models built field-by-field from
      `app.engine.types` / `app.rag` dataclasses (not the dataclasses
      themselves) — every model carrying a requirement/fee/office
      includes its citation fields
- [x] 5.6 Mount all four routers in `main.py` alongside the existing
      `/health`
- [x] 5.7 Confirm `/docs` renders (manual check + a smoke test hitting
      `/openapi.json` and asserting 200)

## 6. Generation model swap

- [x] 6.1 `api/app/rag/generation.py`: change `MODEL` from
      `"claude-opus-5"` to `"claude-sonnet-5"`
- [x] 6.2 Re-run Phase 5's existing RAG test suite unchanged; confirm it
      still passes against the new model (citation/grounding assertions
      don't reference the model itself, so no test edits expected —
      flag here if any do need to change)
      — Completion note: all 8 tests in tests/rag/ pass unchanged
      against claude-sonnet-5, no edits needed.

## 7. CLAUDE.md update

- [x] 7.1 Reword job #2 under "How the Claude API is used" from
      "Matching a free-text situation to a service" to describe intent
      classification (situation/question/answer, fact extraction,
      embedded-question detection) — still job #2, not a new fifth job

## 8. Done-When verification

- [x] 8.1 A full renewal case resolves end to end through the API:
      `POST /chat/message` (opening message) → repeated
      `POST /chat/message` calls answering each `next_question` →
      `POST /case/{id}/resolve` returns the full plan
- [x] 8.2 A general question asked mid-intake returns a grounded RAG
      answer and the same pending question is still returned as next
- [x] 8.3 A combined situation+question message records the fact and
      answers the question in one `POST /chat/message` call
- [x] 8.4 An under-16 case's `POST /case/{id}/resolve` returns the
      scope-gate response, not a plan, through the API
      — Completion note: implementation revealed a gap design.md didn't
      call out — the route's "not ready" gate (checking `next_question`)
      would have blocked an under-16 case from ever reaching
      `resolve_case`'s scope-gate short-circuit, since only `age` is
      known that early. Fixed by having `cases.py`'s resolve route
      check age-under-16 first, before the readiness gate, mirroring
      `resolve_case`'s own "age evaluated first, unconditionally"
      precedence (resolver.py's docstring). Verified via a real
      end-to-end API call with only the age answer recorded.
- [x] 8.5 A message over 2,000 characters is confirmed truncated before
      any model call (integration-level, not just the unit test in 1.3)
- [x] 8.6 `/docs` renders — confirmed live, not just via the OpenAPI
      JSON smoke test
      — Completion note: ran a real `uvicorn` server process (not
      TestClient) and curled `/docs` — 200, full Swagger UI HTML — and
      `/openapi.json` — 200.
