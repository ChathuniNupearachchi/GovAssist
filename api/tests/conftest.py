"""Test fixtures for the engine and RAG test suites.

Runs against the real dev Postgres database (Docker Compose), re-seeded
once per test session from `app.seed.phase4_renewal` (idempotent — wipes
and rebuilds the renewal/amendment services) and
`app.seed.phase5_approve_documents` (idempotent — re-approves the same 8
source documents), so the suite always starts from a known-good state
regardless of what was previously in the dev database. Engine functions
under test are read-only against Requirement/FeeRule/Office/
ResolutionNote/SourceDocument/DocumentChunk, so no per-test transaction
rollback is needed.
"""

import pytest

from app.db.session import SessionLocal
from app.models import Service
from app.seed.phase4_renewal import seed
from app.seed.phase5_approve_documents import approve


@pytest.fixture(scope="session", autouse=True)
def _seeded_database():
    db = SessionLocal()
    try:
        seed(db)
        approve(db)
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
