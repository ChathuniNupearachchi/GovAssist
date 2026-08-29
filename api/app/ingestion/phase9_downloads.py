"""Phase 9: ingests the Downloads page (`pages_e.php?id=24`) and every
PDF it links that this project didn't already have — the overseas
Missions form set (main OM form + 5 conditional annexes), the courier
application, the second (hand-fill) domestic K-35A variant, and the
child-passport request letter.

`pages_e.php?id=24` itself also carries citation-worthy facts beyond
the file list — which downloadable forms must be laser-printed on A4,
and the exact labels distinguishing "Form O" (Amendments & Alterations)
from "Form C" (Children Deletion), new evidence for Conflict 3 (see
design.md).

Fetches each URL (pending), chunks + embeds every one, then approves
all of them — same two-step convention `app.scraper.scraper`/
`app.ingestion.pdf_extraction` (pending) and
`app.seed.phase5_approve_documents` (approve) already established.
Scripted approval, not a human reviewer action, for the same reason
`phase5_approve_documents.py` gives: this content is read directly by a
person (this session) before any rule references it — not a substitute
for the real review workflow Phase 9's admin console will eventually
build.

Idempotent in the same sense `phase5_approve_documents.py` is: re-running
re-fetches (content-addressed snapshots, so identical bytes are a no-op
on disk) and re-approves, but WILL create duplicate SourceDocument/
DocumentChunk rows on a second run (same behavior as `scrape_page`/
`fetch_pdf`, which always insert). Not a concern for this one-off
ingestion — run once.

Run with:  python -m app.ingestion.phase9_downloads
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.db.session import SessionLocal
from app.ingestion.pdf_extraction import fetch_pdf
from app.ingestion.pipeline import chunk_and_embed_source_document
from app.models import SourceDocument
from app.scraper.scraper import scrape_page

DOWNLOADS_PAGE_URL = "https://www.immigration.gov.lk/pages_e.php?id=24"

NEW_PDF_URLS = [
    # Overseas Missions form set (Downloads page section headed
    # "Overseas Missions") — main form + 5 conditional annexes.
    "https://www.immigration.gov.lk/content/files/applications/new_om_application_form.pdf",
    "https://www.immigration.gov.lk/content/files/om/annex_i.pdf",
    "https://www.immigration.gov.lk/content/files/om/annex_ii.pdf",
    "https://www.immigration.gov.lk/content/files/om/annex_iii.pdf",
    "https://www.immigration.gov.lk/content/files/om/annex_iv.pdf",
    "https://www.immigration.gov.lk/content/files/om/annex_v.pdf",
    # Collection gap.
    "https://www.immigration.gov.lk/content/files/applications/CourierSriLankanPassports.pdf",
    # Second domestic form (hand-fill variant of K-35A).
    "https://www.immigration.gov.lk/content/files/applications/application.pdf",
    # Under-16-relevant, previously unknown.
    "https://www.immigration.gov.lk/content/files/applications/request_letter.pdf",
]


def ingest(db) -> list[SourceDocument]:
    documents = [scrape_page(db, DOWNLOADS_PAGE_URL)]
    documents += [fetch_pdf(db, url) for url in NEW_PDF_URLS]

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
