"""Phase 9: ingests `child_deletion_application.pdf` ("Form C" per
id=24, "APPLICATION FOR DELETION OF CHILDREN") for service #6 (Delete
a child's name from a parent's passport) — the one source design.md
flagged as "fetched, read, not yet ingested" and only partially OCR'd
during the original research pass (Tesseract only, Gemini vision
unavailable that session; Sinhala portions garbled, the Rs.250 figure's
context illegible).

Re-ingested via the normal `fetch_pdf`/`chunk_and_embed_source_
document` pipeline, which runs the full free extraction chain
(pdfplumber, then Tesseract, then Gemini vision if Tesseract's quality
check fails) — a fresh attempt in case free-tier quota that blocked
Gemini vision last time has since reset. Not needed to confirm the
LKR 1,200 fee (already independently confirmed by id=10 and
instructions_english_td.pdf, both clean sources) — needed so this
service's form Requirement can cite an actual ingested SourceDocument.

Run with:  python -m app.ingestion.phase9_child_deletion
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.db.session import SessionLocal
from app.ingestion.pdf_extraction import fetch_pdf
from app.ingestion.pipeline import chunk_and_embed_source_document
from app.models import SourceDocument

CHILD_DELETION_FORM_URL = (
    "https://www.immigration.gov.lk/content/files/applications/child_deletion_application.pdf"
)


def ingest(db) -> SourceDocument:
    document = fetch_pdf(db, CHILD_DELETION_FORM_URL)
    chunk_and_embed_source_document(db, document)
    document.status = "approved"
    document.approved_at = datetime.now(timezone.utc)
    db.commit()
    return document


def main() -> None:
    db = SessionLocal()
    try:
        document = ingest(db)
        print(f"Ingested and approved: {document.source_url}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
