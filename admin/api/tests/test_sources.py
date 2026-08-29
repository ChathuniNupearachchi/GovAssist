"""admin-dashboard change, task 7.5 — extraction method surfaces
correctly for a known extraction and a non-PDF document; adding a
source creates no live SOURCE_DOCUMENT/DOCUMENT_CHUNK row."""

from __future__ import annotations

from app.db.session import SessionLocal
from app.models import DocumentChunk, SourceDocument
from tests.conftest import client


def test_source_list_reflects_live_data_with_extraction_method(auth_headers):
    response = client.get("/admin/sources", headers=auth_headers)
    assert response.status_code == 200
    sources = response.json()
    assert sources

    pdf_sources = [s for s in sources if s["document_type"] == "pdf"]
    html_sources = [s for s in sources if s["document_type"] == "html"]

    for s in pdf_sources:
        assert s["extraction_method"] is not None  # "unknown" at worst, never null for a PDF.
    for s in html_sources:
        assert s["extraction_method"] is None


def test_adding_source_creates_overlay_not_live_row(auth_headers):
    db = SessionLocal()
    try:
        source_count_before = db.query(SourceDocument).count()
        chunk_count_before = db.query(DocumentChunk).count()
    finally:
        db.close()

    response = client.post(
        "/admin/sources/overlay",
        json={"source_url": "https://immigration.gov.lk/example-new-circular.pdf", "document_type": "pdf"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["target_id"] is None
    assert body["payload"]["source_url"].endswith("example-new-circular.pdf")

    db = SessionLocal()
    try:
        assert db.query(SourceDocument).count() == source_count_before
        assert db.query(DocumentChunk).count() == chunk_count_before
    finally:
        db.close()
