## 1. Project scaffold

- [x] 1.1 Create `api/` at the repo root with `app/__init__.py`,
      `app/db/__init__.py`, `app/scraper/__init__.py`,
      `app/ingestion/__init__.py`, `app/engine/__init__.py`,
      `app/rag/__init__.py`, `app/api/__init__.py`, and an empty
      `migrations/` directory
- [x] 1.2 Create `api/.gitignore` excluding `venv/`, `__pycache__/`,
      `*.pyc`, `.env`
- [x] 1.3 Update the root `.gitignore` to add `api/venv/` and `api/.env`

## 2. Python environment

- [x] 2.1 Create a Python 3.12 virtual environment at `api/venv`
- [x] 2.2 Write `api/requirements.txt` pinning: fastapi, uvicorn,
      sqlalchemy, alembic, psycopg2-binary, httpx, beautifulsoup4,
      pdfplumber, python-dotenv, pydantic, sentence-transformers,
      anthropic, celery, redis
- [x] 2.3 Install `requirements.txt` into `api/venv` and confirm a clean
      install with no errors

## 3. Docker Compose (Postgres + pgvector, Redis)

- [x] 3.1 Create `docker-compose.yml` at the repo root with a
      `pgvector/pgvector:pg16` service (port 5432, database/user/password
      `govassist`, named volume for data persistence) and a
      `redis:7-alpine` service (port 6379)
- [x] 3.2 Run `docker compose up -d` and confirm both containers report
      healthy / accept connections

## 4. Environment configuration

- [x] 4.1 Create `api/.env` with
      `DATABASE_URL=postgresql://govassist:govassist@localhost:5432/govassist`
      and `REDIS_URL=redis://localhost:6379`
- [x] 4.2 Confirm `api/.env` is excluded by `api/.gitignore` (`git status`
      shows it untracked)

## 5. Database session

- [x] 5.1 Implement `api/app/db/session.py`: SQLAlchemy `engine` and
      `SessionLocal` built from `DATABASE_URL` (loaded via `python-dotenv`),
      plus a `get_db()` FastAPI dependency that yields a session and closes
      it afterward
- [x] 5.2 Do not create `api/app/models.py` in this change — Phase 2 owns
      it

## 6. FastAPI app

- [x] 6.1 Implement `api/main.py`: create the FastAPI app instance and a
      `GET /health` route returning `{"status": "ok"}`
- [x] 6.2 Run `uvicorn main:app --reload` from `api/` and confirm
      `GET /health` returns HTTP 200 with that body

## 7. Alembic

- [x] 7.1 Run `alembic init migrations` inside `api/` (matches the
      `migrations/` directory from task 1.1) and generate `alembic.ini`
- [x] 7.2 Edit `migrations/env.py` to load `.env` via `python-dotenv` and
      set `sqlalchemy.url` from `DATABASE_URL` at runtime, and set
      `target_metadata` to `app.models.Base.metadata` for autogenerate
      (this import will only resolve once Phase 2 creates `app/models.py`
      — do not add a placeholder model here to work around it)
- [x] 7.3 Do not run `alembic revision --autogenerate` or
      `alembic upgrade head` in this change — no models exist yet

## 8. Verification (Done-when criteria)

- [x] 8.1 `docker compose up -d` starts both containers successfully from a
      clean checkout
- [x] 8.2 `uvicorn main:app --reload` serves `GET /health` returning 200
- [x] 8.3 Alembic is initialised (`alembic.ini` + `migrations/env.py`
      present and configured) and ready for Phase 2 to generate its
      migration against
- [x] 8.4 `pip install -r api/requirements.txt` succeeds in a fresh venv on
      a second machine/checkout
- [x] 8.5 `git status` at the repo root shows no `.env`, `venv/`, or
      `__pycache__/` paths as trackable/untracked-but-would-be-added