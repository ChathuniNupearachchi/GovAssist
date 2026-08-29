"""admin-dashboard change — shared test fixtures: a `TestClient` over
the real `/admin/api` app (connected as `govassist_admin_readonly`
against the dev database, per this project's existing test convention
of testing against the real dev Postgres rather than mocking it) and a
freshly signed-up admin per test to avoid cross-test email collisions.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.fixture()
def admin_token() -> str:
    email = f"admin-{uuid.uuid4().hex[:12]}@example.test"
    response = client.post(
        "/admin/auth/signup", json={"email": email, "password": "correct horse battery staple", "role": "reviewer"}
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


@pytest.fixture()
def auth_headers(admin_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {admin_token}"}
