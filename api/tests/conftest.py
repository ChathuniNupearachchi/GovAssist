"""Test fixtures for the engine test suite.

Runs against the real dev Postgres database (Docker Compose), re-seeded
once per test session from `app.seed.phase4_renewal` — that seed script
is idempotent (it wipes and rebuilds the renewal/amendment services), so
the suite always starts from a known-good state regardless of what was
previously in the dev database. Engine functions under test are
read-only against Requirement/FeeRule/Office/ResolutionNote, so no
per-test transaction rollback is needed.
"""

import pytest

from app.db.session import SessionLocal
from app.models import Service
from app.seed.phase4_renewal import seed


@pytest.fixture(scope="session", autouse=True)
def _seeded_database():
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def renewal_service_id(db):
    return db.query(Service).filter(Service.code == "passport-renewal").first().id
