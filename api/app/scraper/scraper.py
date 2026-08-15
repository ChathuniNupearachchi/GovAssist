"""HTML page scraper — fetches target pages and persists them as pending
SourceDocuments, snapshot-before-parsing (see fetch.py)."""

from datetime import datetime

from sqlalchemy.orm import Session

from app.models import SourceDocument
from app.scraper.config import TARGET_PAGES
from app.scraper.fetch import fetch_and_snapshot


def scrape_page(db: Session, url: str) -> SourceDocument:
    """Fetch one page, snapshot it, and persist it as a pending SourceDocument."""
    content_hash, snapshot_path = fetch_and_snapshot(url, extension=".html")

    document = SourceDocument(
        source_url=url,
        snapshot_path=snapshot_path,
        content_hash=content_hash,
        document_type="html",
        fetched_at=datetime.utcnow(),
        status="pending",
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def scrape_all_targets(db: Session) -> list[SourceDocument]:
    """Fetch every configured target page."""
    return [scrape_page(db, url) for url in TARGET_PAGES]
