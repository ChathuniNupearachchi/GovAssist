"""admin-dashboard change, task 6.6 — all seven live services appear
with correct counts and approved status; an overlay edit appears in
the dashboard view and leaves live rule tables unchanged."""

from __future__ import annotations

from app.db.session import SessionLocal
from app.models import Requirement, RuleVersion, Service
from tests.conftest import client

_EXPECTED_CODES = {
    "passport-renewal",
    "passport-new",
    "passport-lost-stolen",
    "passport-amendment",
    "passport-under-16",
    "passport-child-deletion",
    "emergency-certificate",
}


def test_all_seven_services_appear_approved_with_real_counts(auth_headers):
    response = client.get("/admin/services", headers=auth_headers)
    assert response.status_code == 200
    services = response.json()

    codes = {s["code"] for s in services}
    assert _EXPECTED_CODES.issubset(codes)

    for s in services:
        if s["code"] in _EXPECTED_CODES:
            assert s["current_rule_version_status"] == "approved"
            assert s["requirement_count"] > 0


def test_drill_down_matches_live_data(auth_headers):
    services = client.get("/admin/services", headers=auth_headers).json()
    renewal = next(s for s in services if s["code"] == "passport-renewal")

    response = client.get(f"/admin/services/{renewal['id']}", headers=auth_headers)
    assert response.status_code == 200
    detail = response.json()

    assert len(detail["requirements"]) == renewal["requirement_count"]
    for requirement in detail["requirements"]:
        assert requirement["citation"]["source_url"]


def test_overlay_edit_recorded_and_live_table_unchanged(auth_headers):
    db = SessionLocal()
    try:
        service = db.query(Service).filter(Service.code == "passport-renewal").first()
        rule_version = (
            db.query(RuleVersion)
            .filter(RuleVersion.service_id == service.id, RuleVersion.status == "approved")
            .first()
        )
        requirement_count_before = (
            db.query(Requirement).filter(Requirement.rule_version_id == rule_version.id).count()
        )
        service_id = str(service.id)
    finally:
        db.close()

    response = client.post(
        f"/admin/services/{service_id}/overlay",
        json={"operation": "update", "payload": {"name": "Renew an Ordinary Passport (proposed rename)"}},
        headers=auth_headers,
    )
    assert response.status_code == 201
    assert response.json()["payload"]["name"] == "Renew an Ordinary Passport (proposed rename)"

    detail = client.get(f"/admin/services/{service_id}", headers=auth_headers).json()
    assert any(
        o["operation"] == "update" and o["payload"].get("name", "").endswith("(proposed rename)")
        for o in detail["overlays"]
    )

    db = SessionLocal()
    try:
        service_after = db.get(Service, service_id)
        assert service_after.name == "Renew an Ordinary Passport"
        requirement_count_after = (
            db.query(Requirement).filter(Requirement.rule_version_id == rule_version.id).count()
        )
        assert requirement_count_after == requirement_count_before
    finally:
        db.close()
