## Context

Greenfield backend — nothing exists under `api/` yet (the prior
`setup-fastapi-backend` change was deleted, superseded by this one). See
proposal.md - Why for how this fits BACKEND_PLAN.md's phase ordering. The
folder structure below is BACKEND_PLAN.md 1.3's, taken as given rather than
re-derived.

## Goals / Non-Goals

**Goals:**
- `docker compose up -d` starts both the Postgres/pgvector and Redis
  containers.
- `uvicorn main:app --reload` serves `GET /health`.
- Alembic is initialised, points at `app.models.Base.metadata`, and reads
  `DATABASE_URL` from `.env` — ready for Phase 2 to generate its migration
  against, without needing any Alembic setup work in Phase 2.
- A clean `pip install -r requirements.txt` on a fresh machine/venv.

**Non-Goals:**
- No SQLAlchemy models, no Alembic migration, no tables. `app/models.py`
  does not exist yet — Alembic's `target_metadata` points at
  `app.models.Base.metadata`, and Phase 2 is what creates that module.
- No scraper, ingestion, rules engine, or RAG code — the `scraper/`,
  `ingestion/`, `engine/`, `rag/`, `api/` subpackages under `app/` are
  created empty (just `__init__.py`) so Phase 2 onward have a place to land
  without another structural change.
- No Redis client code and no Celery worker — `redis` and `celery` are
  pinned in `requirements.txt` and `REDIS_URL` is set in `.env` per
  BACKEND_PLAN.md 1.2, but nothing in this change connects to Redis or
  runs a Celery task. That starts in whichever phase first needs a queue
  (BACKEND_PLAN.md Phase 8).
- No `anthropic` or `sentence-transformers` usage — both are installed now
  (BACKEND_PLAN.md 1.2) but not imported by any code in this change.

## Decisions

**`app/models.py` does not exist in this change, but `alembic/env.py` is
still configured to import `app.models.Base.metadata`.** Since the module
doesn't exist yet, this import would fail if Alembic actually ran
`--autogenerate` right now — that's expected and fine, because this
change's Done-when criteria only requires Alembic to be *initialised and
ready*, not to have generated or applied a migration. Phase 2 creates
`app/models.py` and is the first phase that actually runs
`alembic revision --autogenerate`. This is the one sequencing detail worth
flagging explicitly so Phase 2 doesn't need to touch `alembic/env.py` at
all — it should already be correctly wired.

**Folder layout matches BACKEND_PLAN.md 1.3 exactly**, including the empty
`engine/` and `rag/` packages that the now-deleted `setup-fastapi-backend`
change's design deferred creating. Since BACKEND_PLAN.md explicitly lists
them for Phase 1, they're created now rather than deferred again —
BACKEND_PLAN.md is the authoritative phase plan for this project, so its
explicit folder list wins over the earlier change's more conservative
"create packages only when their phase needs them" reasoning.

**`docker-compose.yml` adds a `redis:7-alpine` service alongside Postgres**,
matching BACKEND_PLAN.md 1.1. No named volume for Redis — it's used as a
cache/broker in later phases, not for data that needs to survive a
container restart in local dev.

**Alembic reads `DATABASE_URL` from `.env` via `python-dotenv` inside
`alembic/env.py`**, overriding `sqlalchemy.url` from `alembic.ini` at
runtime, rather than hardcoding the URL in `alembic.ini` — same reasoning
as the deleted change's design: one source of truth for the connection
string.

**Health check is DB-agnostic.** `GET /health` returns `{"status": "ok"}`
without querying the database, verifying "the process is up" independent
of "the database is reachable." Not required to change for this phase.

## Risks / Trade-offs

- [`api/.env` holds a local-only, non-secret placeholder password
  (`govassist`/`govassist`) that becomes a real secret in any shared
  environment] → `.env` is gitignored from the start; deployment
  environments must set `DATABASE_URL`/`REDIS_URL` themselves, never
  inherit this file.
- [`alembic/env.py` importing `app.models.Base` before that module exists
  is a latent break if anyone runs `alembic revision --autogenerate`
  before Phase 2] → acceptable: the Done-when criteria for this change is
  "initialised and ready," not "autogenerate succeeds." Flagged above so
  Phase 2 knows this is expected, not a bug to debug.
- [Installing `sentence-transformers`, `anthropic`, `celery`, `redis` now
  with no code using them yet risks them silently going stale/mismatched
  by the time their phase arrives] → low risk over a short phase gap;
  cheaper than re-deriving the pinned versions per-phase, and
  BACKEND_PLAN.md explicitly asks for them here.

## Migration Plan

1. `docker compose up -d` — start Postgres/pgvector and Redis.
2. Create `api/venv`, install `requirements.txt`.
3. `uvicorn main:app --reload` — confirm `/health`.
4. `alembic init migrations` inside `api/`, wire `env.py` to `.env` and
   `app.models.Base.metadata` — do not run `revision --autogenerate` (no
   models exist yet).

No existing data or running service to migrate — first deploy. Rollback is
`docker compose down -v` to discard the local containers/volume entirely.