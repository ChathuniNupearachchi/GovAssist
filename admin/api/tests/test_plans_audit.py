"""admin-dashboard change, task 8.3 — a case resolved against a since-
superseded rule version is flagged outdated; a case still on the
current approved version is not.

Builds a deterministic fixture with raw SQL over the citizen system's
own database role (`api/.env`'s `DATABASE_URL`, a superuser-equivalent
role with full read/write on live tables) rather than through
`govassist_admin_readonly` — the whole point of that role's grants is
that it CANNOT create this fixture itself (see admin-data-access spec),
so a test proving the audit view's outdated computation needs a
different, test-only path to set up live data, exactly like this
project's existing seed scripts do. Plain psycopg2, not this project's
ORM, since importing the citizen system's `app` package from this
process collides with `/admin/api`'s own `app` package name (see
`app/models.py`'s docstring).
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime

import psycopg2
import pytest
from dotenv import dotenv_values

from tests.conftest import client

_CITIZEN_ENV = dotenv_values(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "api", ".env")
)
_CITIZEN_DATABASE_URL = _CITIZEN_ENV.get("DATABASE_URL")


def _citizen_connect():
    return psycopg2.connect(_CITIZEN_DATABASE_URL)


@pytest.fixture()
def superseded_case():
    """Creates: a second, newer `approved` RULE_VERSION for
    passport-renewal (superseding the existing one), and a resolved
    `CASE` + `PLAN_ITEM` pointing at the ORIGINAL (now-superseded) rule
    version — the exact shape admin-plan-audit's "a plan built on a
    superseded version" scenario describes. Cleans up everything it
    created, and restores the original version's `approved` status,
    regardless of test outcome.
    """
    if not _CITIZEN_DATABASE_URL:
        pytest.skip("api/.env not found or has no DATABASE_URL — can't build the fixture.")

    conn = _citizen_connect()
    conn.autocommit = True
    cur = conn.cursor()

    cur.execute(
        "SELECT id, version_number FROM rule_version WHERE service_id = "
        "(SELECT id FROM service WHERE code = 'passport-renewal') AND status = 'approved' "
        "ORDER BY version_number DESC LIMIT 1"
    )
    original_rule_version_id, original_version_number = cur.fetchone()

    cur.execute("SELECT id FROM requirement WHERE rule_version_id = %s LIMIT 1", (original_rule_version_id,))
    row = cur.fetchone()
    if row is None:
        conn.close()
        pytest.skip("passport-renewal's approved rule version has no requirements to attach a plan item to.")
    requirement_id = row[0]

    cur.execute("SELECT id FROM service WHERE code = 'passport-renewal'")
    (service_id,) = cur.fetchone()
    cur.execute("SELECT id, source_document_id FROM rule_version WHERE id = %s", (original_rule_version_id,))
    _, source_document_id = cur.fetchone()

    new_rule_version_id = str(uuid.uuid4())
    case_id = str(uuid.uuid4())
    plan_item_id = str(uuid.uuid4())

    try:
        cur.execute(
            "INSERT INTO rule_version (id, service_id, source_document_id, version_number, status, verified_at) "
            "VALUES (%s, %s, %s, %s, 'approved', now())",
            (new_rule_version_id, service_id, source_document_id, original_version_number + 1),
        )
        cur.execute(
            "INSERT INTO \"case\" (id, service_id, device_ref, resolved_at, outdated) "
            "VALUES (%s, %s, %s, %s, false)",
            (case_id, service_id, "admin-dashboard-test-device", datetime.utcnow()),
        )
        cur.execute(
            "INSERT INTO plan_item (id, case_id, requirement_id, rule_version_id, collected, sequence) "
            "VALUES (%s, %s, %s, %s, false, 1)",
            (plan_item_id, case_id, requirement_id, original_rule_version_id),
        )

        yield {"case_id": case_id, "original_version_number": original_version_number}
    finally:
        cur.execute("DELETE FROM plan_item WHERE id = %s", (plan_item_id,))
        cur.execute("DELETE FROM \"case\" WHERE id = %s", (case_id,))
        cur.execute("DELETE FROM rule_version WHERE id = %s", (new_rule_version_id,))
        conn.close()


def test_case_on_superseded_version_flagged_outdated(auth_headers, superseded_case):
    response = client.get("/admin/plans/audit", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()

    entry = next((e for e in body if e["case_id"] == superseded_case["case_id"]), None)
    assert entry is not None, "fixture case not found in audit view"
    assert entry["outdated"] is True
    assert entry["resolved_rule_version_number"] == superseded_case["original_version_number"]
    assert entry["current_approved_rule_version_number"] == superseded_case["original_version_number"] + 1


def test_case_on_current_version_not_flagged_outdated(auth_headers):
    response = client.get("/admin/plans/audit", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()

    current_version_cases = [
        e
        for e in body
        if e["current_approved_rule_version_number"] == e["resolved_rule_version_number"]
    ]
    if not current_version_cases:
        pytest.skip("No case currently resolved against its service's current approved version.")
    for entry in current_version_cases:
        assert entry["outdated"] is False
