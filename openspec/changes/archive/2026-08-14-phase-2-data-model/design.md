## Context

`api/app/models.py` does not exist. Phase 1 (`api/migrations/env.py`)
already imports `app.models.Base` and was verified to fail at exactly that
import — this change is what makes it resolve. See proposal.md - Why for
how this fits BACKEND_PLAN.md's phase ordering. Nothing downstream
(scraper, ingestion, rules engine, RAG, API routes) exists yet either;
this schema is built for their future use, not against any current
caller.

## Goals / Non-Goals

**Goals:**
- All 14 tables from BACKEND_PLAN.md Phase 2's list exist after
  `alembic upgrade head`, in one migration (BACKEND_PLAN.md's heading says
  "Thirteen tables in one Alembic migration," but its own list names 14 —
  see proposal.md's correction note; confirmed with the user to build all
  14, including `REQUIREMENT_CONDITION`).
- `alembic downgrade -1` removes exactly what the migration added.
- Every one of Sri Lanka's 25 districts resolves to exactly one seeded
  accepting office via a plain query — no application code required to
  prove it.
- `CONDITION.operator` is restricted to `equals` / `lessThan` / `in`, and
  the schema has no self-reference that would allow condition nesting.
- `DOCUMENT_CHUNK.embedding` is a pgvector `vector(384)` column, and the
  `vector` extension is enabled as part of this migration (Phase 1 chose
  the pgvector Postgres image but never ran `CREATE EXTENSION`).

**Non-Goals:**
- No application logic reading or writing these tables — no scraper, no
  ingestion, no rules engine, no RAG, no API routes. BACKEND_PLAN.md
  Phase 4.4 ("Office resolver... urgent goes to Head Office only,
  otherwise district mapping") is explicitly a later phase; this change
  only provides the data that resolver will read.
- No `ds` or `mission` office rows — BACKEND_PLAN.md's seed list only
  names the head office and five regional offices. The `type` column
  supports `ds`/`mission` for whenever real data for those exists.
- No admin authentication — `ADMIN_USER` is a table, not a login system
  (BACKEND_PLAN.md Phase 9).

## Decisions

**UUID primary keys via `sqlalchemy.dialects.postgresql.UUID(as_uuid=True)`
with a Python-side `uuid4` default**, matching the pattern the (now
superseded) earlier backend change established, for the same reason: works
identically in tests, no dependency on a Postgres-side UUID extension.

**Enum-like columns (`status`, `kind`, `type`, `operator`, `answer_type`,
`role`, `basis`, `document_type`) are plain `String` with a Postgres
`CHECK` constraint enumerating the allowed values, not a native Postgres
`ENUM` type.** A `CHECK` constraint is one `ALTER TABLE` to extend later;
a Postgres `ENUM` type needs `ALTER TYPE ... ADD VALUE` plus, in older
Postgres, a transaction-boundary workaround. BACKEND_PLAN.md's later
phases (change detection, admin review) are likely to add status values;
optimizing for that is worth the slightly weaker type safety versus a
native enum.

**`OFFICE.district` is `ARRAY(String)`, not a single scalar, and there is
no separate "district mapping" table beyond BACKEND_PLAN.md's 14.**
BACKEND_PLAN.md's column list names a single `district` column but
doesn't fix its cardinality, and the Done-when criterion ("every district
resolves to an accepting office") needs one office to serve multiple
districts — the five regional offices can't cover 25 districts
one-to-one. An array column keeps the district directory queryable in one
column (`WHERE :district = ANY(district)`) without adding a 15th table.
- Alternative: add a `DISTRICT_OFFICE` join table. Rejected — the user
  confirmed the table list is exactly BACKEND_PLAN.md's 14, and a
  scalar-per-row array is sufficient for a lookup this simple (25 rows,
  static).
- Alternative: keep `district` scalar (one office = one district) and
  resolve unmapped districts to the nearest office in application code
  later. Rejected — the Done-when criterion requires this phase to prove
  resolution by data alone, not defer it to Phase 4 logic.

**Foreign keys default to `RESTRICT` on delete (SQLAlchemy/Postgres
default), not `CASCADE`.** This schema is an audit trail as much as
working data — a rule version, requirement, or case should never
silently disappear because something it references was deleted. Nothing
in this phase deletes rows anyway; this is a guardrail for later phases.

**Seed data (offices + district mapping) is inserted inside the same
migration's `upgrade()`, via `op.bulk_insert`, and removed in
`downgrade()` by deleting those specific seeded rows** (not a blanket
`DELETE FROM office`, so a future migration that adds more offices doesn't
get its rows wiped by this one's downgrade).

**The `vector` extension is enabled with
`op.execute("CREATE EXTENSION IF NOT EXISTS vector")` at the top of
`upgrade()`**, guarded by `IF NOT EXISTS` since the pgvector Docker image
makes the extension available but does not enable it automatically.
`downgrade()` drops it back with `DROP EXTENSION IF EXISTS vector` —
required for the reversibility requirement's "no orphaned ... extensions"
to actually hold, and safe here since nothing else in this project uses
the extension yet.

**District-to-office assignment is a reasonable placeholder, not sourced
from an official Immigration Department jurisdiction list.** The 25
districts are distributed across the five regional offices by rough
geographic proximity (see tasks.md for the exact assignment). This
satisfies the Done-when criterion (every district resolves to *some*
office) but is explicitly not verified content — per CLAUDE.md's content
rules, this must be corrected against a real source before it's ever
citizen-facing. Flagged in Risks below and as a task, not silently
assumed correct.

## Risks / Trade-offs

- [District-to-office seed data is a geographic approximation, not sourced
  from an official Immigration Department jurisdiction list] → acceptable
  for this phase's Done-when criterion (data exists, every district
  resolves), but must be replaced with verified data before any
  citizen-facing office routing ships. Tracked as a follow-up, not silently
  treated as final.
- [`String` + `CHECK` constraint gives weaker guarantees than a native
  enum or an application-level `Enum` class — a raw SQL `INSERT` could
  still violate the intended value set if the `CHECK` is ever dropped] →
  acceptable trade-off for migration flexibility; the SQLAlchemy model
  layer also uses Python `Enum`/`Literal` types so ORM-level writes are
  still type-checked before they ever reach the `CHECK` constraint.
- [One migration creating 14 tables plus seed data is a large,
  all-or-nothing unit] → matches BACKEND_PLAN.md's explicit instruction
  ("Thirteen tables in one Alembic migration" — one migration, per the
  count correction above); mitigated by the reversibility requirement
  (`downgrade -1` removes it all cleanly) rather than needing
  partial-failure recovery.
- [`ARRAY(String)` for `OFFICE.district` is a non-obvious reading of
  BACKEND_PLAN.md's terse column list] → documented here and in the spec
  precisely because it's a judgment call, not a literal transcription.

## Migration Plan

1. Add `pgvector` to `api/requirements.txt`, install it.
2. Write `api/app/models.py`: `Base` + all 14 models.
3. Generate the migration:
   `alembic revision --autogenerate -m "create phase 2 data model"` —
   confirm `env.py`'s `from app.models import Base` now resolves (Phase 1
   left this import deliberately unresolved; this is the change that
   fixes it).
4. Hand-edit the generated migration to add the `CREATE EXTENSION vector`
   statement and the seed-data inserts (autogenerate won't produce
   either).
5. `alembic upgrade head` against the local Docker Postgres; verify all
   14 tables, the extension, and the seed rows.
6. `alembic downgrade -1`; verify a clean rollback (no tables, no seed
   rows, `vector` extension dropped).

No existing data — this is the first schema this database has ever had
past Phase 1's empty state.