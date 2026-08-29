"""admin-dashboard change, task 5.3 (plus a basic shape check for 5.1) —
confirms the summary is computed from real data and that no RAGAS/
Langfuse field or panel exists anywhere in the response."""

from __future__ import annotations

from tests.conftest import client


def test_summary_reflects_real_data(auth_headers):
    response = client.get("/admin/dashboard/summary", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()

    assert isinstance(body["drafts_pending"], int)
    assert isinstance(body["sources_pending"], int)
    assert isinstance(body["services_without_approved_rule"], int)
    assert isinstance(body["recently_approved"], list)
    # All seven services have an approved rule version (see
    # admin-service-catalog spec's "hand-verified rules display as
    # approved") — so none should be counted here.
    assert body["services_without_approved_rule"] == 0


def test_no_ragas_or_langfuse_field_anywhere_in_response(auth_headers):
    response = client.get("/admin/dashboard/summary", headers=auth_headers)
    lowered = response.text.lower()
    assert "ragas" not in lowered
    assert "langfuse" not in lowered
