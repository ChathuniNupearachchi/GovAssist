"""Seven-corrections round: ingests `om_01_2019.pdf` (Immigration
Circular OM/01/2019, "Revised Charges for Issuance of Sri Lankan Travel
Documents") — provided locally at content/files/circulars/om_01_2019.pdf,
not fetched from a URL (see this module's own `_fetch_local_pdf`). Scanned,
no text layer; OCR'd via the existing free chain (Tesseract succeeded here,
quality-check passed) and cross-checked against a second, independent
Gemini vision pass before any figure was trusted — both agreed on every
fee in the table. See design.md's "Timelines" section and the seven-
corrections round's own report for the full transcript.

`pages_e.php?id=9` (the fingerprint/BDA source for item 1) and
`pages_e.php?id=8` (the dual-citizen/lost-passport sources for items 4
and 6) are already ingested from earlier phases — this script only adds
the one genuinely new source.

Same fetch/chunk/embed/approve pattern as `app.ingestion.phase9_downloads`.

Run with:  python -m app.ingestion.phase9_seven_corrections
"""

from __future__ import annotations

import hashlib
import shutil
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from app.db.session import SessionLocal
from app.ingestion.pipeline import chunk_and_embed_source_document
from app.models import SourceDocument
from app.scraper.fetch import SNAPSHOT_DIR

# Mirrors the real site's asset path structure (content/files/<category>/
# <file>) — every other local PDF in this project maps to its
# immigration.gov.lk URL the same way (see app.ingestion.config.TARGET_PDFS).
CIRCULAR_URL = "https://www.immigration.gov.lk/content/files/circulars/om_01_2019.pdf"
CIRCULAR_LOCAL_PATH = (
    Path(__file__).resolve().parents[3] / "content" / "files" / "circulars" / "om_01_2019.pdf"
)


def _fetch_local_pdf(db, url: str, local_path: Path) -> SourceDocument:
    """Local-file variant of `app.ingestion.pdf_extraction.fetch_pdf` —
    content-addressed the same way, just sourced from a file already on
    disk instead of an HTTP fetch. Idempotent: returns the existing row
    if this URL was already ingested."""
    existing = db.scalars(select(SourceDocument).where(SourceDocument.source_url == url)).first()
    if existing is not None:
        return existing

    raw_bytes = local_path.read_bytes()
    content_hash = hashlib.sha256(raw_bytes).hexdigest()
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    absolute_path = SNAPSHOT_DIR / f"{content_hash}.pdf"
    if not absolute_path.exists():
        shutil.copy(local_path, absolute_path)

    document = SourceDocument(
        source_url=url,
        snapshot_path=str(absolute_path.relative_to(Path(".").resolve())),
        content_hash=content_hash,
        document_type="pdf",
        fetched_at=datetime.now(timezone.utc),
        status="pending",
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def ingest(db) -> list[SourceDocument]:
    document = _fetch_local_pdf(db, CIRCULAR_URL, CIRCULAR_LOCAL_PATH)
    if document.status != "approved":
        chunk_and_embed_source_document(db, document)
        document.status = "approved"
        document.approved_at = datetime.now(timezone.utc)
        db.commit()
    return [document]


def main() -> None:
    db = SessionLocal()
    try:
        documents = ingest(db)
        print(f"Ingested and approved {len(documents)} source document(s):")
        for doc in documents:
            print(f"  {doc.source_url}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
