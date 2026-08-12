## 1. Project scaffold

- [ ] 1.1 Create `api/` at the repo root with `app/__init__.py`,
      `app/db/__init__.py`, `app/scraper/__init__.py`,
      `app/ingestion/__init__.py`, and an empty `migrations/` directory
- [ ] 1.2 Create `api/.gitignore` excluding `venv/`, `__pycache__/`, `*.pyc`,
      `.env`
- [ ] 1.3 Update the root `.gitignore` to add `api/venv/` and `api/.env`

## 2. Python environment

- [ ] 2.1 Create a Python 3.12 virtual environment at `api/venv`
- [ ] 2.2 Write `api/requirements.txt` pinning: fastapi, uvicorn,
      sqlalchemy, alembic, psycopg2-binary, httpx, beautifulsoup4,
      pdfplumber, python-dotenv
- [ ] 2.3 Install `requirements.txt` into `api/venv` and confirm a clean
      install with no errors

## 3. Docker Compose (Postgres + pgvector)

- [ ] 3.1 Create `docker-compose.yml` at the repo root with a
      `pgvector/pgvector:pg16` service, port 5432 exposed, database/user/
      password all `govassist`, and a named volume for data persistence
- [ ] 3.2 Run `docker compose up -d` and confirm the container reports
      healthy / accepts connections

## 4. Environment configuration

- [ ] 4.1 Create `api/.env` with
      `DATABASE_URL=postgresql://govassist:govassist@localhost:5432/govassist`
- [ ] 4.2 Confirm `api/.env` is excluded by `api/.gitignore` (`git status`
      shows it untracked)

## 5. Database session and model

- [ ] 5.1 Implement `api/app/db/session.py`: SQLAlchemy `engine` and
      `SessionLocal` built from `DATABASE_URL` (loaded via `python-dotenv`),
      plus a `get_db()` FastAPI dependency that yields a session and closes
      it afterward
- [ ] 5.2 Implement `api/app/models.py`: declarative `Base` and the
      `SourceDocument` model — UUID primary key (Python-side default),
      `source_url` (String, not null), `content_hash` (String, not null),
      `raw_content` (Text, not null), `document_type` (String, default
      `"html"`), `fetched_at` (DateTime, default `utcnow`), `status`
      (String, default `"pending"`)

## 6. FastAPI app

- [ ] 6.1 Implement `api/main.py`: create the FastAPI app instance and a
      `GET /health` route returning `{"status": "ok"}`
- [ ] 6.2 Run `uvicorn main:app --reload` from `api/` and confirm
      `GET /health` returns HTTP 200 with that body

## 7. Alembic

- [ ] 7.1 Run `alembic init migrations` inside `api/` (matches the
      `migrations/` directory from task 1.1) and generate `alembic.ini`
- [ ] 7.2 Edit `migrations/env.py` to load `.env` via `python-dotenv` and
      set `sqlalchemy.url` from `DATABASE_URL` at runtime, and set
      `target_metadata` to `app.models.Base.metadata` for autogenerate
- [ ] 7.3 Generate the initial migration with
      `alembic revision --autogenerate -m "create source_documents table"`
      and review the generated script matches the model in task 5.2
- [ ] 7.4 Run `alembic upgrade head` against the Docker Postgres instance
      and confirm the `source_documents` table exists with the expected
      columns

## 8. Verification (Done-when criteria)

- [ ] 8.1 `docker compose up -d` starts Postgres successfully from a clean
      checkout
- [ ] 8.2 `alembic upgrade head` creates the `source_documents` table
- [ ] 8.3 `uvicorn main:app --reload` serves `GET /health` returning 200
- [ ] 8.4 `pip install -r api/requirements.txt` succeeds in a fresh venv on
      a second machine/checkout
- [ ] 8.5 `git status` at the repo root shows no `.env`, `venv/`, or
      `__pycache__/` paths as trackable/untracked-but-would-be-added
