## Context

See proposal.md for motivation. This phase wires together, over HTTP,
work that was previously only reachable from tests: Phase 4's
`app.engine.resolver.resolve_case` / `next_question`, and Phase 5's
`app.rag.answer.answer_question`. Neither changes its own resolution
logic in this phase.

`api/app/api/` already exists (created empty in Phase 1) and currently
holds nothing but `__init__.py`. `main.py` currently defines `/health`
inline and nothing else.

## Goals / Non-Goals

**Goals:**
- A real, storable conversation drives a real, computed plan through
  HTTP alone.
- Every citizen message is bounded before it reaches any model.
- The plan/RAG boundary (CLAUDE.md's "Two kinds of question, two
  mechanisms") holds at the API layer, not just inside the engine.

**Non-Goals:**
- No rate limiting implementation — CLAUDE.md's "All endpoints that
  call the LLM are rate-limited" is satisfied by Phase 8's Nginx layer,
  per BACKEND_PLAN.md's own phasing (Phase 8's cut-order list even
  allows cutting Nginx rate limiting if behind schedule, confirming it
  isn't meant to gate Phase 6). Documented here so it isn't mistaken
  for an oversight.
- No Redis caching (Phase 8), no auth/JWT (Phase 9), no admin routes.
- No new engine or RAG behavior — this phase only routes to what
  Phases 4–5 already built.

## Decisions

### Case creation needs a `device_ref`; `POST /chat/message` carries one
`Case.device_ref` is `NOT NULL` (Phase 2 schema — device-only storage
per CLAUDE.md, no citizen accounts). `POST /chat/message`'s request body
is `{message: str, case_id: UUID | None, device_ref: str}` —
`device_ref` is required when `case_id` is omitted (creating a case) and
ignored when an existing case is referenced. A new case is always
created against the `passport-renewal` service — the only intake-driven
service this build has.

### Deterministic pass: a per-attribute matcher table, not a generic type check
`Question.answer_type` has only three values (`single`/`boolean`/
`district`), but `single` covers `age` (numeric), `profession` (free
text, always accepted), and `service_basis` (an enum of normal/urgent) —
three different matching rules under one formal type. Rather than widen
`answer_type` (a Phase 2 schema already closed, and unnecessary — this
is a routing-layer concern, not a persistence one), `api/app/chat/
deterministic.py` keys a small matcher table by `attribute` (the same
vocabulary `app.engine.renewal_intake.RENEWAL_QUESTIONS` already
defines): `age` → bare integer, `service_basis` → `normal`/`urgent` +
close synonyms, `district` → exact match against the seeded district
list, the five boolean attributes → a yes/no lexicon, `profession` →
any non-empty message (free text is always a valid profession answer).
A message matches the deterministic pass only when, after
strip/lowercase, it consists **solely** of a plausible answer token —
anything with surrounding prose falls through to the Claude classifier,
per the spec's "message with surrounding prose" scenario.

### Classification: structured output, Claude Haiku 4.5, a confidence threshold
The classifier calls `claude-haiku-4-5` with `output_config.format` set
to a JSON schema: `{intent: "situation"|"question"|"answer", extracted:
{[attribute]: string}, contains_question: bool, confidence: number}`.
`confidence` is elicited from the model itself (0–1); a fixed threshold
(0.6) below which the router overrides `intent` to `"question"` and
discards any `extracted` facts, per the spec's low-confidence
requirement. The threshold is a single named constant, not scattered,
matching Phase 5's `WEAK_MATCH_THRESHOLD` precedent — it may need
recalibration once real citizen messages are seen, same as retrieval's
threshold did.

### Generation moves to Claude Sonnet 5, per explicit instruction
Phase 5's `generation.py` hardcoded `claude-opus-5`. This phase changes
it to `claude-sonnet-5`, per this phase's explicit "Use claude-sonnet
for grounded generation." Confirmed this is a code change only: the
`rag-answering` spec's requirements describe grounding, citation, and
refusal behavior — never a specific model — so no spec delta is needed
for the swap, and Phase 5's own tests (which assert on citation shape
and grounding, not on `response.model`) remain valid unchanged.

### `/chat/message` routes intent uniformly through "record" and "answer"
Every classification outcome (deterministic match, or Claude
`situation`/`answer`/`question`, with or without `contains_question`)
reduces to two independent actions the router may take in the same
turn: record `extracted` facts as case answers (if any), and answer via
RAG (if `contains_question` or intent is `question`). This is why a
combined situation+question message needs no special case — it is
just "both actions happen this turn," exactly matching Phase 4/5's
"engine resolves, RAG answers, never mixed" boundary applied per-turn
rather than per-message.

### `/case/{id}/resolve` does not itself drive intake
`POST /case/{id}/resolve` calls `app.engine.resolver.resolve_case` with
the case's recorded answers assembled into the same `{attribute: value}`
dict shape the engine already expects (via the same `ATTRIBUTE_BY_PROMPT`
reverse-lookup `next_question.py` already uses). If `next_question`
would return non-null (an answer is still missing), `resolve` returns a
4xx-class "not ready" response naming the still-pending question rather
than letting `resolve_case`'s `ValueError` (on a missing `age`) leak
through as an unhandled 500. This keeps `POST /chat/message` and
`POST /case/{id}/resolve` cleanly separated, matching the phase's own
route list rather than having chat silently auto-resolve.

### FastAPI structure
`api/app/api/chat.py`, `cases.py`, `services.py`, `requirements.py` —
one `APIRouter` each, mounted in `main.py` alongside the existing
`/health`. Response bodies are Pydantic models built from the engine's
and RAG's existing dataclasses (`app.engine.types.Citation`,
`ResolvedRequirement`, etc.) via field-by-field construction, not by
making the dataclasses themselves Pydantic models — keeps the engine
and RAG packages framework-agnostic, consistent with their Phase 4/5
design ("build and test in isolation").

## Risks / Trade-offs

- [Risk] The 0.6 confidence threshold is unvalidated against real
  citizen phrasing (Phase 4/5's precedent: thresholds tuned once tend
  to need a second pass once real usage arrives). → Mitigation: same
  approach as `WEAK_MATCH_THRESHOLD` — one named constant, documented
  as a future tuning target, not asserted as final.
- [Risk] The deterministic pass's per-attribute matcher table is
  specific to the 9 renewal questions; adding a second service's intake
  later means extending it, not a generic solution. → Accepted for this
  phase — there is exactly one intake-driven service today, and
  generalizing before a second service exists would be speculative.
- [Risk] No rate limiting means a malicious or buggy client could drive
  unbounded Claude API spend through `/chat/message` before Phase 8
  ships. → Accepted per BACKEND_PLAN.md's explicit phasing; flagged
  here rather than silently deferred.

## Migration Plan

No schema changes. No migration. Purely additive code: new routers, a
new `chat` package, one constant change in an existing file
(`generation.py`'s `MODEL`), and a CLAUDE.md wording update.
