## Why

The mobile app (`govassist/`) currently has no backend to talk to. Before the
scraper and PDF extraction pipeline can be built, the project needs a running
FastAPI service, a Postgres database it can connect to, and a place to land
scraped source documents. This change lays that foundation only — no scraping
or PDF logic yet.

## What Changes

- Add an `api/` FastAPI project (Python 3.12) at the repo root, sibling to
  `govassist/`.
- Add `docker-compose.yml` at the repo root running Postgres 16 with pgvector
  for local development.
- Add a `SourceDocument` SQLAlchemy model that records the raw scraped
  content, a content hash, a fetch timestamp, and a review status — the
  storage shape the (future) scraper and ingestion pipeline will write to.
- Wire up Alembic migrations against that model and generate the initial
  migration.
- Add a minimal `GET /health` endpoint to confirm the service is alive.
- Add `api/.gitignore` and update the root `.gitignore` so no secrets or
  virtualenv files are committed.

Out of scope for this change: the scraper itself, PDF extraction, the rule
engine, Redis/Celery, and any citizen-facing endpoint. Those are separate,
later changes per CLAUDE.md's backend structure.

## Capabilities

### New Capabilities
- `backend-service`: the FastAPI application skeleton — process entrypoint,
  environment-driven configuration, database session wiring, and a health
  check endpoint.
- `source-document-storage`: the persisted record of a scraped source
  document, including the change-detection fields (content hash, fetch
  timestamp) and the pending/approved/rejected review lifecycle required
  before any scraped content can be treated as a verified source.

### Modified Capabilities
(none — this is greenfield backend work)

## Impact

- New directory: `api/` (FastAPI app, Alembic migrations, requirements.txt,
  venv, `.env`).
- New file: `docker-compose.yml` at repo root.
- Root `.gitignore` gains `api/venv/` and `api/.env` entries.
- No changes to `govassist/` mobile app code.
- New local dependency: Docker (for Postgres/pgvector) and Python 3.12 with
  the packages pinned in `api/requirements.txt`.
