"""admin-dashboard change, task 4.8 — pending queue includes the
seeded draft; comparison flags the fee change as material; approve
writes only ADMIN_ACTION and leaves RULE_VERSION.status unchanged;
reject requires and stores a reason and leaves the draft visible."""

from __future__ import annotations

from app.db.session import SessionLocal
from app.models import AdminDraft, RuleVersion, Service
from tests.conftest import client


def _reset_draft_status_to_pending(draft_id: str) -> None:
    """Restores the seeded draft's own status after a test exercises
    approve/reject on it, so later tests (and re-runs of this suite)
    still find it pending — done via admin's own writable-table grant
    directly, not by re-running the citizen system's seed script (which
    lives in `api/app/seed`, a package this process can't import — see
    `app/models.py`'s docstring on the `app` package-name collision)."""
    db = SessionLocal()
    try:
        draft = db.get(AdminDraft, draft_id)
        draft.status = "pending"
        db.commit()
    finally:
        db.close()


def _seeded_renewal_draft_id(auth_headers: dict) -> str:
    pending = client.get("/admin/rules/pending", headers=auth_headers).json()
    renewal_drafts = [
        p for p in pending if p["source"] == "admin_draft" and p["service_code"] == "passport-renewal"
    ]
    assert renewal_drafts, f"seeded renewal draft not found in {pending}"
    return renewal_drafts[0]["id"]


def test_pending_queue_includes_seeded_draft(auth_headers):
    pending = client.get("/admin/rules/pending", headers=auth_headers).json()
    assert any(p["source"] == "admin_draft" for p in pending)


def test_comparison_flags_fee_change_as_material(auth_headers):
    draft_id = _seeded_renewal_draft_id(auth_headers)
    response = client.get(f"/admin/rules/pending/{draft_id}", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()

    assert body["approved"]["fee"]["base_amount"] == 10000.0
    assert body["draft"]["fee"]["base_amount"] == 12000.0

    fee_diffs = [d for d in body["diffs"] if d["field"] == "fee.base_amount"]
    assert fee_diffs, body["diffs"]
    assert fee_diffs[0]["materiality"] == "material"
    assert fee_diffs[0]["approved_value"] == 10000.0
    assert fee_diffs[0]["draft_value"] == 12000.0


def test_approve_records_action_and_leaves_live_rule_version_unchanged(auth_headers):
    db = SessionLocal()
    try:
        service = db.query(Service).filter(Service.code == "passport-renewal").first()
        rule_version_before = (
            db.query(RuleVersion)
            .filter(RuleVersion.service_id == service.id, RuleVersion.status == "approved")
            .first()
        )
        status_before = rule_version_before.status
    finally:
        db.close()

    draft_id = _seeded_renewal_draft_id(auth_headers)
    response = client.post(f"/admin/rules/pending/{draft_id}/approve", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "approved"

    db = SessionLocal()
    try:
        rule_version_after = db.get(RuleVersion, rule_version_before.id)
        assert rule_version_after.status == status_before == "approved"
    finally:
        db.close()

    _reset_draft_status_to_pending(draft_id)


def test_reject_requires_reason_and_preserves_draft(auth_headers):
    draft_id = _seeded_renewal_draft_id(auth_headers)

    missing_reason = client.post(f"/admin/rules/pending/{draft_id}/reject", json={"reason": "   "}, headers=auth_headers)
    assert missing_reason.status_code == 422

    response = client.post(
        f"/admin/rules/pending/{draft_id}/reject",
        json={"reason": "Fee increase needs finance sign-off first"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"
    assert response.json()["reason"] == "Fee increase needs finance sign-off first"

    # Still visible in the pending queue, never deleted.
    pending = client.get("/admin/rules/pending", headers=auth_headers).json()
    assert any(p["id"] == draft_id for p in pending)

    _reset_draft_status_to_pending(draft_id)
