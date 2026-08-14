## Why

BACKEND_PLAN.md Phase 2 is the dependency root for every backend phase
after Phase 1: the rules engine (Phase 4), ingestion pipeline (Phase 3),
and RAG layer (Phase 5) all read and write the same tables. Nothing past
this point can be built or even meaningfully specced until that schema
exists. Phase 1 deliberately left `app/models.py` undefined for exactly
this change to create.

**Correction to BACKEND_PLAN.md**: its Phase 2 heading says "Thirteen
tables," but the list underneath it names 14 — `SERVICE`,
`SOURCE_DOCUMENT`, `RULE_VERSION`, `REQUIREMENT`, `CONDITION`,
`REQUIREMENT_CONDITION`, `FEE_RULE`, `QUESTION`, `OFFICE`, `CASE`,
`CASE_ANSWER`, `PLAN_ITEM`, `DOCUMENT_CHUNK`, `ADMIN_USER`. Confirmed with
the user: build all 14 listed, including `REQUIREMENT_CONDITION` (the one
entry without its own `id`, and the likely source of the miscount). This
change's artifacts use "14" throughout; BACKEND_PLAN.md's own heading
text is quoted as-is where referenced, not silently corrected.

## What Changes

- Create `api/app/models.py` fresh: the declarative `Base` and all 14 ORM
  models from BACKEND_PLAN.md Phase 2 — `SERVICE`, `SOURCE_DOCUMENT`,
  `RULE_VERSION`, `REQUIREMENT`, `CONDITION`, `REQUIREMENT_CONDITION`,
  `FEE_RULE`, `QUESTION`, `OFFICE`, `CASE`, `CASE_ANSWER`, `PLAN_ITEM`,
  `DOCUMENT_CHUNK`, `ADMIN_USER`.
- Generate one Alembic migration creating all 14 tables, enabling the
  pgvector extension, and seeding the office directory.
- Seed data: Head Office (Battaramulla), five regional offices (Kandy,
  Matara, Vavuniya, Kurunegala, Jaffna), and a district-to-office mapping
  covering all 25 Sri Lankan districts.
- `CONDITION.operator` is restricted to exactly three values (`equals`,
  `lessThan`, `in`); conditions do not nest and are not composed with
  AND/OR — `REQUIREMENT_CONDITION` links a requirement to a flat set of
  conditions, all of which must hold.
- `DOCUMENT_CHUNK.embedding` is a pgvector `vector(384)` column.

`SOURCE_DOCUMENT`'s shape here (`source_url`, `snapshot_path`,
`content_hash`, `document_type`, `fetched_at`, `status`) is
BACKEND_PLAN.md's Phase 2 definition, not the shape from the earlier,
now-superseded `setup-fastapi-backend` change (which had a different
column, `raw_content`, and was deleted before ever being applied — see
its replacement, `phase-1-backend-foundation`). This change is the first
and only place `SOURCE_DOCUMENT` actually gets built.

Explicitly out of scope: any application logic that reads or writes these
tables (scraper, ingestion, rules engine, RAG, API routes) — this change
is schema and seed data only, per BACKEND_PLAN.md's phase split.

## Capabilities

### New Capabilities
- `case-resolution-data-model`: the persisted shape of a service's rules,
  their versioning and approval trail, the requirements/conditions/fees
  they resolve to, intake questions, case resolution and plan output, and
  source document chunks — everything Phases 3–6 will read and write.
- `office-directory`: the persisted office directory and the guarantee
  that every citizen's district resolves to exactly one accepting office.

### Modified Capabilities
(none — `backend-service` from Phase 1 is unaffected; this change only
adds `app/models.py`, which Phase 1's Alembic wiring already expected)

## Impact

- New file: `api/app/models.py` (declarative `Base` + 14 models).
- New Alembic migration under `api/migrations/versions/`.
- `api/migrations/env.py`'s `from app.models import Base` (added in
  Phase 1, previously failing) now resolves.
- Local Postgres database gains 14 tables, the `vector` extension enabled,
  and seed rows in `office`.
- New Python dependency: `pgvector` (the SQLAlchemy `Vector` column type)
  added to `api/requirements.txt` — Phase 1 installed a pgvector-capable
  Postgres image but not this Python package, since nothing needed a
  vector column until now.
- No changes to `govassist/` mobile app code.