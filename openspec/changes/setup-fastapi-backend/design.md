## Context

Greenfield backend — nothing exists under `api/` yet. CLAUDE.md's backend
stack (see `/CLAUDE.md`) names the full eventual toolset (Redis, Celery,
sentence-transformers, MCP server, `engine/` rule resolver, `models/` as a
package). This change builds only the slice needed before the scraper and
PDF extraction can start: a running service, a database, and the
`SourceDocument` storage shape. Everything else in CLAUDE.md's stack list is
out of scope until its own change.

## Goals / Non-Goals

**Goals:**
- `docker compose up -d` brings up a Postgres 16 + pgvector instance the
  backend can reach.
- `alembic upgrade head` creates the `source_documents` table matching the
  `SourceDocument` model.
- `uvicorn main:app --reload` serves `GET /health`.
- A clean `pip install -r requirements.txt` on a fresh machine/venv.

**Non-Goals:**
- No scraper, PDF extraction, rule engine, or MCP server code.
- No Redis/Celery — nothing here is async/queued yet.
- No auth, no citizen-facing or reviewer-facing endpoints beyond `/health`.
- No pgvector-backed table yet (the extension is enabled at the DB level so
  later changes can add vector columns without a fresh migration to enable
  it, but nothing uses it in this change).

## Decisions

**Folder layout matches the user's literal scope, not CLAUDE.md's full
eventual layout.** CLAUDE.md's project structure section (written for the
finished backend) shows `models/`, `engine/`, `mcp/` as packages. This
change creates only `app/models.py` (single file), `app/db/`,
`app/scraper/` (empty package), and `app/ingestion/` (empty package) — the
two empty packages exist now so the scraper and ingestion changes have a
place to land without another structural change. `engine/`, `mcp/`, and
splitting `models.py` into a package are deferred to the changes that
actually need them, to avoid scaffolding unused structure.
- Alternative considered: build the full CLAUDE.md tree now. Rejected —
  empty packages with no code are churn, and the split of `models.py` into
  a package is a mechanical change to make later if/when there are enough
  models to warrant it.

**UUID primary key via `sqlalchemy.dialects.postgresql.UUID(as_uuid=True)`
with a Python-side `uuid4` default**, not a Postgres-side
`gen_random_uuid()` default. Keeps ID generation working identically in
tests (e.g. SQLite) and avoids depending on the `pgcrypto`/`uuid-ossp`
extension being enabled. Alembic's autogenerate handles this cleanly since
the default lives in the model, not a DB-side function.

**`content_hash` is computed by the caller (future scraper), not the
model.** The model just stores whatever string it's given. Hashing
algorithm choice (sha256 is the obvious pick) belongs to the scraper change,
not this foundation.

**Alembic reads `DATABASE_URL` from `.env` via `python-dotenv` inside
`alembic/env.py`**, overriding `sqlalchemy.url` from `alembic.ini` at
runtime, rather than hardcoding the URL in `alembic.ini`. Keeps one source
of truth for the connection string (`.env`) instead of two files that can
drift.

**pgvector enabled via `docker-compose.yml`'s image choice
(`pgvector/pgvector:pg16`) only** — no `CREATE EXTENSION vector` migration
in this change, since nothing here has a vector column yet. The image
ships the extension available to be enabled by whichever future migration
first needs it.

**Health check is DB-agnostic.** `GET /health` returns `{"status": "ok"}`
without querying the database, so it verifies "the process is up" (useful
for container liveness) independent of "the database is reachable". A
future readiness probe can add a DB round trip if needed — not required by
this change's Done-when criteria.

## Risks / Trade-offs

- [`api/.env` holds a local-only, non-secret placeholder password
  (`govassist`/`govassist`) that becomes a real secret in any shared
  environment] → `.env` is gitignored from the start; deployment
  environments (Railway per CLAUDE.md) must set `DATABASE_URL` themselves,
  never inherit this file.
- [Empty `scraper/` and `ingestion/` packages with no code could bit-rot or
  invite premature structure] → each contains only an `__init__.py`; the
  proposal explicitly scopes actual scraper/ingestion logic to future
  changes.
- [SQLite is not used anywhere in this change, but the UUID/default choice
  above was made with future test-suite portability in mind] → no action
  needed now; flagged so a future testing-setup change doesn't have to
  revisit the model.

## Migration Plan

1. `docker compose up -d` — start Postgres/pgvector.
2. Create `api/venv`, install `requirements.txt`.
3. `alembic upgrade head` — create `source_documents`.
4. `uvicorn main:app --reload` — confirm `/health`.

No existing data or running service to migrate — this is a first deploy of
the table. Rollback is `alembic downgrade -1` (drops `source_documents`) or
`docker compose down -v` to discard the local database entirely.
