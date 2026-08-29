"""admin-dashboard change, task 10.2 — the explicit, scripted proof that
approving a draft through the admin dashboard has zero effect on what a
citizen sees, per design.md's "Verifying 'citizen-facing query returns
exactly what it returned before'" decision:

  1. Build a resolved renewal case directly in the live database (the
     citizen system's own credentials, via plain SQL — this script sets
     up a fixture, it doesn't stand in for the citizen app).
  2. Call the citizen-facing `POST /case/{id}/resolve` and save the
     response.
  3. Sign in to `/admin/api` and approve the seeded renewal fee-change
     draft.
  4. Call the same citizen-facing endpoint again and save the response.
  5. Assert the two captures are byte-identical.
  6. Clean up the fixture case; leave the draft's dashboard-only
     "approved" status as the visible proof of step 3.

Talks to both API processes over plain HTTP and to Postgres over plain
psycopg2 — no import of either app's own `app` package, so this script
has no exposure to the `app`-name collision documented in
`admin/api/app/models.py`. Requires both servers running:
  citizen API:  uvicorn main:app --port 8000   (from /api)
  admin API:    uvicorn app.main:app --port 8001 (from /admin/api)

Run with:  python admin/scripts/verify_isolation.py
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
import requests
from dotenv import dotenv_values

REPO_ROOT = Path(__file__).resolve().parents[2]
CITIZEN_API = "http://localhost:8000"
ADMIN_API = "http://localhost:8001"
OUT_DIR = Path(__file__).resolve().parent.parent / "verification"

_CITIZEN_ENV = dotenv_values(REPO_ROOT / "api" / ".env")
_CITIZEN_DATABASE_URL = _CITIZEN_ENV.get("DATABASE_URL")

# Same representative renewal answer set the seed script itself uses to
# build the draft's payload (api/app/seed/admin_dashboard_draft.py).
_ANSWER_VALUES = {
    "age": "30",
    "applying_from": "sri_lanka",
    "holds_passport": "true",
    "name_changed": "false",
    "dual_citizen": "false",
    "section_19_2": "false",
    "buddhist_priest": "false",
    "profession": "",
    "district": "colombo",
    "photo_district": "colombo",
    "service_basis": "normal",
}


def _connect():
    if not _CITIZEN_DATABASE_URL:
        raise RuntimeError("api/.env has no DATABASE_URL — can't build the fixture case.")
    return psycopg2.connect(_CITIZEN_DATABASE_URL)


def build_fixture_case(conn) -> str:
    cur = conn.cursor()
    cur.execute("SELECT id FROM service WHERE code = 'passport-renewal'")
    (service_id,) = cur.fetchone()

    cur.execute("SELECT id, prompt FROM question WHERE service_id = %s", (service_id,))
    question_rows = cur.fetchall()

    case_id = str(uuid.uuid4())
    cur.execute(
        "INSERT INTO \"case\" (id, service_id, device_ref, resolved_at, outdated) "
        "VALUES (%s, %s, %s, NULL, false)",
        (case_id, service_id, "verify-isolation-script"),
    )

    prompt_to_attribute = {
        "How old is the applicant?": "age",
        "Are you applying from inside Sri Lanka, or from abroad?": "applying_from",
        "Do you still hold your current or a previous passport?": "holds_passport",
        "Has your name changed since your passport was issued?": "name_changed",
        "Are you a dual citizen?": "dual_citizen",
        "Did you apply for dual citizenship through the special provisions route, rather than the standard application?": "section_19_2",
        "Are you a Buddhist priest?": "buddhist_priest",
        "What is your job or occupation? (leave blank if you don't have one)": "profession",
        "Which district are you applying from?": "district",
        "Which district will you take your passport photograph in?": "photo_district",
        "Do you need normal service, or urgent (same-day) service?": "service_basis",
    }

    for question_id, prompt in question_rows:
        attribute = prompt_to_attribute.get(prompt)
        if attribute is None or attribute not in _ANSWER_VALUES:
            continue
        cur.execute(
            "INSERT INTO case_answer (id, case_id, question_id, value) VALUES (%s, %s, %s, %s)",
            (str(uuid.uuid4()), case_id, str(question_id), _ANSWER_VALUES[attribute]),
        )

    conn.commit()
    return case_id


def cleanup_fixture_case(conn, case_id: str) -> None:
    cur = conn.cursor()
    cur.execute("DELETE FROM plan_item WHERE case_id = %s", (case_id,))
    cur.execute("DELETE FROM case_answer WHERE case_id = %s", (case_id,))
    cur.execute("DELETE FROM \"case\" WHERE id = %s", (case_id,))
    conn.commit()


def resolve_case(case_id: str) -> requests.Response:
    return requests.post(f"{CITIZEN_API}/case/{case_id}/resolve", timeout=30)


def approve_seeded_draft() -> None:
    email = f"verify-isolation-{uuid.uuid4().hex[:10]}@example.test"
    signup = requests.post(
        f"{ADMIN_API}/admin/auth/signup",
        json={"email": email, "password": "correct horse battery staple", "role": "approver"},
        timeout=15,
    )
    signup.raise_for_status()
    token = signup.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    pending = requests.get(f"{ADMIN_API}/admin/rules/pending", headers=headers, timeout=15).json()
    renewal_draft = next(
        p for p in pending if p["source"] == "admin_draft" and p["service_code"] == "passport-renewal"
    )
    response = requests.post(
        f"{ADMIN_API}/admin/rules/pending/{renewal_draft['id']}/approve", headers=headers, timeout=15
    )
    response.raise_for_status()
    print(f"Approved draft {renewal_draft['id']} via admin dashboard (dashboard-only status change).")


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    conn = _connect()
    case_id = build_fixture_case(conn)
    print(f"Built fixture case {case_id} for passport-renewal.")

    try:
        before = resolve_case(case_id)
        before.raise_for_status()
        before_path = OUT_DIR / "citizen_resolve_before_approval.json"
        before_path.write_text(before.text, encoding="utf-8")
        print(f"Captured before-approval resolution -> {before_path}")

        approve_seeded_draft()

        after = resolve_case(case_id)
        after.raise_for_status()
        after_path = OUT_DIR / "citizen_resolve_after_approval.json"
        after_path.write_text(after.text, encoding="utf-8")
        print(f"Captured after-approval resolution -> {after_path}")

        identical = before.text == after.text
        summary = {
            "identical": identical,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "case_id": case_id,
        }
        (OUT_DIR / "result.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

        if identical:
            print("PASS: citizen-facing /case/{id}/resolve is byte-identical before and after the admin approval.")
        else:
            print("FAIL: citizen-facing responses differ before/after the admin approval.")
        return 0 if identical else 1
    finally:
        cleanup_fixture_case(conn, case_id)
        conn.close()
        print(f"Cleaned up fixture case {case_id}.")


if __name__ == "__main__":
    sys.exit(main())
