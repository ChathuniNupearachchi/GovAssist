"""Phase 5 seed data: approve the ingested corpus for RAG retrieval.

No SourceDocument has ever been approved — Phase 9's admin review
console doesn't exist yet. Retrieval must scope strictly to approved
documents (phase-5-rag-layer's rag-answering spec), so without this
step retrieval has nothing to return.

Approves the first-fetch SourceDocument for each of the 8 ingested URLs
(5 HTML + 3 PDF), by source_url ordered by fetched_at ascending — the
same stability convention Phase 4 established for citations. The
second-fetch row for each HTML URL (Phase 3's re-scrape, differing only
by a live visitor counter) is left pending and is never approved —
approving it too would let retrieval return duplicate chunks for the
same content.

This is a scripted approval, not a human reviewer action — justified
because this content was already directly verified against the live
site in Phase 3 and Phase 4 (see design.md's Context). It is explicitly
not a substitute for the real review workflow Phase 9 will build.

Idempotent: re-running updates approved_at to "now" on the same 8 rows
rather than accumulating anything.

Run with:  python -m app.seed.phase5_approve_documents
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import SourceDocument

INGESTED_URL_SUBSTRINGS = [
    "pages_e.php?id=7",
    "pages_e.php?id=8",
    "pages_e.php?id=9",
    "pages_e.php?id=10",
    "studio_e.php",
    "content/files/applications/instructions_english_td.pdf",
    "content/files/applications/passport_application.pdf",
    "content/files/applications/amendment.pdf",
]


def approve(db: Session) -> list[SourceDocument]:
    now = datetime.now(timezone.utc)
    approved = []
    for url_substring in INGESTED_URL_SUBSTRINGS:
        doc = db.scalars(
            select(SourceDocument)
            .where(SourceDocument.source_url.like(f"%{url_substring}"))
            .order_by(SourceDocument.fetched_at.asc())
        ).first()
        if doc is None:
            raise RuntimeError(
                f"No ingested SourceDocument found for '{url_substring}' — "
                "run Phase 3's scraper before approving Phase 5's corpus."
            )
        doc.status = "approved"
        doc.approved_at = now
        approved.append(doc)
    db.commit()
    return approved


def main() -> None:
    db = SessionLocal()
    try:
        approved = approve(db)
        print(f"Approved {len(approved)} source documents:")
        for doc in approved:
            print(f"  {doc.source_url}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
