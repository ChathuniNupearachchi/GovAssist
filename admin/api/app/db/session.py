"""admin-dashboard change: /admin/api's own database engine and
session, entirely separate from `/api/app/db/session.py` — bound to
`ADMIN_DATABASE_URL`, the dedicated `govassist_admin_readonly` role's
connection string (admin/api/.env), not `/api`'s `DATABASE_URL`.

Per design.md's "Database-level read-only enforcement via a dedicated
Postgres role": every query this session issues against a live table
is enforced read-only by Postgres itself, regardless of what the
application code above it does. Writes only ever succeed against the
four admin-owned tables the role has CRUD grants on.

`app.models` (the ORM class definitions) is imported from the citizen
system's `api/app` package — the schema and its Alembic migration
history are single-sourced there (see `api/migrations/env.py`'s own
precedent for adding `api/` to `sys.path`), not duplicated here. This
is a shared *schema definition*, not a shared *route or session* — the
citizen-facing app never imports anything from `/admin`, and this
module's own engine/session/credentials are entirely independent of
`/api`'s.
"""

import os
import sys
from collections.abc import Generator
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Make the citizen system's `api/` importable for its `app.models`
# module only — see module docstring.
_API_ROOT = Path(__file__).resolve().parents[4] / "api"
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

load_dotenv()

ADMIN_DATABASE_URL = os.environ["ADMIN_DATABASE_URL"]

engine = create_engine(ADMIN_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session (connected as
    `govassist_admin_readonly`) and closes it after use."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
