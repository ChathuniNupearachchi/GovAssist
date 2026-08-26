"""Phase 9: ingests the two sources design.md's service #3 (Replace a
lost or stolen passport) needed but that were only "fetched, read, not
yet ingested" during the original research pass — `pages_e.php?id=12`
(the reporting/cancellation process) and the domestic-adjacent
complaint-form PDF. `om/annex_iv.pdf` (the overseas complaint form) and
`id=8`/`instructions_english_td.pdf` (the replacement-document/fee
facts) are already ingested from earlier phases.

Same fetch/chunk/embed/approve pattern as `app.ingestion.phase9_downloads`
— see that module's docstring for the scripted-approval justification.

Run with:  python -m app.ingestion.phase9_lost_stolen
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.db.session import SessionLocal
from app.ingestion.pdf_extraction import fetch_pdf
from app.ingestion.pipeline import chunk_and_embed_source_document
from app.models import SourceDocument
from app.scraper.scraper import scrape_page

ID_12_URL = "https://www.immigration.gov.lk/pages_e.php?id=12"
# NB: the site's own filename has spaces, URL-encoded as %20 — see
# app.ingestion.sources's note on this exact URL.
COMPLAINT_FORM_URL = (
    "https://www.immigration.gov.lk/content/files/applications/"
    "complaint_form%20_stolen_and_lost_sri%20lankan_passport.pdf"
)


def ingest(db) -> list[SourceDocument]:
    documents = [scrape_page(db, ID_12_URL), fetch_pdf(db, COMPLAINT_FORM_URL)]

    for document in documents:
        chunk_and_embed_source_document(db, document)

    now = datetime.now(timezone.utc)
    for document in documents:
        document.status = "approved"
        document.approved_at = now
    db.commit()

    return documents


def main() -> None:
    db = SessionLocal()
    try:
        documents = ingest(db)
        print(f"Ingested and approved {len(documents)} source documents:")
        for doc in documents:
            print(f"  {doc.source_url}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
