## Why

BACKEND_PLAN.md's Phase 1 is the dependency root for every later backend
phase (data model, ingestion, rules engine, RAG, API routes) — nothing else
can be built until there is a running FastAPI service, a reachable
Postgres/pgvector instance, a Redis instance, and Alembic wired up to
autogenerate from the (still-empty) model base. This change builds exactly
that foundation and nothing past it — Phase 2's thirteen-table data model
is explicitly out of scope here.

This supersedes the earlier `setup-fastapi-backend` change, which planned
to also create the `SourceDocument` model now. BACKEND_PLAN.md's phase
split puts all data modelling in Phase 2, so that work has been removed
from this change's scope; the old change was deleted rather than kept
alongside this one to avoid two open proposals with contradictory scope
for the same `api/` scaffold.

## What Changes

- Add `docker-compose.yml` at the repo root: Postgres 16 + pgvector and
  Redis 7, per BACKEND_PLAN.md 1.1.
- Add the `api/` FastAPI project scaffold (Python 3.12): `main.py`,
  `requirements.txt`, `.env`, `.gitignore`, `alembic.ini`, `migrations/`,
  and the `app/` package with `db/`, `scraper/`, `ingestion/`, `engine/`,
  `rag/`, `api/` subpackages (empty except `db/session.py`) — per
  BACKEND_PLAN.md 1.2–1.3.
- Add `GET /health` returning `{"status": "ok"}`.
- Add SQLAlchemy `engine`/`SessionLocal`/`get_db()` reading `DATABASE_URL`
  from `.env`.
- Initialise Alembic, reading `DATABASE_URL` from `.env` and targeting
  `app.models.Base.metadata` for autogenerate — but generate no migration
  and create no tables yet, since `app/models.py` defines no models in
  this change.
- Update root and `api/.gitignore` so no secrets/venv are committed.

Explicitly out of scope (per BACKEND_PLAN.md's phase split): any
SQLAlchemy model, any Alembic migration, the scraper, ingestion, rules
engine, or RAG logic, and any endpoint beyond `/health`. `requirements.txt`
pins `sentence-transformers`, `anthropic`, `celery`, and `redis` now
because BACKEND_PLAN.md 1.2 lists them as part of Phase 1's environment,
but no code in this change imports or uses them yet — they're installed,
not wired up.

## Capabilities

### New Capabilities
- `backend-service`: the FastAPI application skeleton — process
  entrypoint, environment-driven configuration, database session wiring,
  and a health check endpoint. (Same capability name the deleted
  `setup-fastapi-backend` change used; no archived spec exists yet, so
  there is nothing to conflict with.)

### Modified Capabilities
(none)

## Impact

- New directory: `api/` (FastAPI app, empty subpackages, Alembic scaffold,
  `requirements.txt`, venv, `.env`).
- New file: `docker-compose.yml` at repo root.
- Root `.gitignore` gains `api/venv/` and `api/.env` entries.
- No changes to `govassist/` mobile app code.
- New local dependencies: Docker (Postgres/pgvector + Redis containers)
  and Python 3.12 with the packages pinned in `api/requirements.txt`.
- No database tables exist after this change — `alembic upgrade head` has
  nothing to apply yet (Alembic is initialised and ready, per the Done-when
  criteria, not run against a real migration).