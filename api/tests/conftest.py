"""Test fixtures for the engine and RAG test suites.

Runs against the real dev Postgres database (Docker Compose), re-seeded
once per test session, in order, from: `app.seed.phase4_renewal`
(idempotent — wipes and rebuilds `passport-renewal`; also clears any
`passport-amendment` rows but no longer seeds that service itself),
`app.seed.phase5_approve_documents` (idempotent — re-approves the
original 8 source documents; every service's own newly ingested
sources — id=24, the OM form set, id=12, etc. — are approved directly
by their own `app.ingestion.phase9_*` script at ingestion time, not by
this one), `app.seed.phase9_new_applicant` (`passport-new`, design.md
service #2), `app.seed.phase9_lost_stolen` (`passport-lost-stolen`,
service #3), `app.seed.phase9_amendment` (`passport-amendment`, service
#4 — MUST run after phase4_renewal, which still clears this service's
rows on every run). So the suite always starts from a known-good state
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
from app.seed.phase9_new_applicant import seed as seed_new_applicant
from app.seed.phase9_lost_stolen import seed as seed_lost_stolen
from app.seed.phase9_amendment import seed as seed_amendment
from app.seed.phase9_under_16 import seed as seed_under_16
from app.seed.phase9_child_deletion import seed as seed_child_deletion
from app.seed.phase9_emergency_certificate import seed as seed_emergency_certificate


@pytest.fixture(scope="session", autouse=True)
def _seeded_database():
    db = SessionLocal()
    try:
        seed(db)
        approve(db)
        seed_new_applicant(db)
        seed_lost_stolen(db)
        seed_amendment(db)
        seed_under_16(db)
        seed_child_deletion(db)
        seed_emergency_certificate(db)
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


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """`pytest.ini`'s `addopts = -m "not real_api"` skips every real-API
    test by default (langgraph-orchestration-branch's "mock external API
    calls by default" decision) — deselected items don't show up in the
    normal pass/fail/skip counts at all, so without this the coverage gap
    would be silent. Reports the count explicitly instead: "Report
    skipped tests rather than hiding them, so the coverage gap stays
    visible.\""""
    deselected = len(getattr(terminalreporter, "stats", {}).get("deselected", []))
    if deselected:
        terminalreporter.write_line(
            f"\n{deselected} real-API test(s) skipped by default (marker: real_api) - "
            f"run `pytest -m real_api` to include them.",
            yellow=True,
        )
