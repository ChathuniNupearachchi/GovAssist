## Why

Phases 1–3 built the schema and the ingestion pipeline, but no service has
real rules yet — there is nothing for a citizen to resolve against. Phase 4
makes adult passport renewal the first fully-worked service: the renewal
rules are hand-entered as cited, approved data, and the engine that
resolves a citizen's answers against that data is built and unit-tested in
isolation, with no API routes yet (Phase 6). This is the proof that "rules
live in data, not code" actually holds for a real, source-conflicted,
branching government process — not just a schema diagram.

## What Changes

- **BREAKING**: `REQUIREMENT` and `FEE_RULE` gain their own
  `source_document_id` (nullable FK to `SOURCE_DOCUMENT`), decoupled from
  `RULE_VERSION.source_document_id`. Discovered while hand-entering
  renewal data: the renewal service's facts span two documents
  (`pages_e.php?id=8` for documents/fees/offices, `pages_e.php?id=7` for
  the fingerprints prerequisite and the office conflict), but the existing
  schema lets a rule version cite only one document, shared by everything
  under it. `RULE_VERSION.source_document_id` remains as the version's
  primary citation; the new columns are the specific per-fact attribution.
- **New table `RESOLUTION_NOTE`**: holds an advisory note attached to
  resolution (not a document/step/prerequisite a citizen collects), with
  up to two source document citations. First use: the office resolver's
  urgent-service conflict note. Confirmed with the user this is
  citizen-facing (it changes what the citizen does before traveling) and
  must live in data so a future conflict in another department is an
  insert, not a code change.
- Hand-enter adult passport renewal as one approved `RULE_VERSION`
  (`pages_e.php?id=8` primary citation): the standard document set, the
  dual-citizen document set (replaces the standard set, not additive),
  fees (normal/urgent), the office submission list, and the two
  `pages_e.php?id=7`-sourced prerequisites (photo studio acknowledgement
  before application, fingerprints in person for ages 16–60).
- Hand-enter a second, lightweight approved `RULE_VERSION` for a new
  `passport-amendment` service (`pages_e.php?id=10` citation): the
  change-of-name alteration fee and its two required documents. Exists so
  the renewal engine can surface it as a real, data-backed alternative
  when a name change is detected — not a hardcoded fact.
- Seed one `RESOLUTION_NOTE`: the urgent-service office conflict, citing
  both the "only available at Head Office" passage and the regional
  one-day-service working-hours passage on `pages_e.php?id=7`.
- Build the rules engine (`api/app/engine/`): condition evaluator,
  requirement resolver (standard vs. dual-citizen set selection),
  fee calculator, office resolver (deterministic precedence + conflict
  note attachment, never routes to a DS office), prerequisite ordering,
  next-question logic, and the under-16 scope gate.
- Ten golden-scenario tests (`api/tests/`) with hand-verified expected
  output, run in CI, failing the build on regression.
- No API routes, no chat intake UI. Engine functions only, called
  directly from tests.

## Capabilities

### New Capabilities
- `renewal-rule-data`: the hand-entered, cited, approved rule content for
  adult passport renewal and passport amendment — what data must exist,
  not how it resolves.
- `case-resolution-engine`: the engine that evaluates conditions, resolves
  requirements/fees/offices/prerequisites/next-question against a case's
  answers, gates under-16 cases, and surfaces the amendment alternative.

### Modified Capabilities
- `case-resolution-data-model`: `REQUIREMENT` and `FEE_RULE` gain their
  own `source_document_id`; new `RESOLUTION_NOTE` table; migration
  rollback scenario updated from 14 to 15 tables.

## Impact

- `api/app/models.py` — `Requirement.source_document_id`,
  `FeeRule.source_document_id`, new `ResolutionNote` model.
- New Alembic migration adding the two columns and the new table.
- `api/app/engine/` — new package: `conditions.py`, `requirements.py`,
  `fees.py`, `offices.py`, `prerequisites.py`, `next_question.py`.
- `api/app/seed/` (or a one-off script) — inserts the renewal and
  amendment rule data described above; run once against the dev database.
- `api/tests/engine/` — unit tests per component plus the golden set.
- No changes to the mobile app, RAG layer, or API routes in this phase.
