"""SQLAlchemy engine and session wiring.

Reads DATABASE_URL from the environment (loaded from api/.env via
python-dotenv) so the same code can point at different databases
(local Docker Postgres, CI, production) without a code change.

The declarative Base and all ORM models live in app/models.py, added in
Phase 2 — this module only wires up the engine/session, not the schema.
"""

import os
from collections.abc import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session and closes it after use."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()