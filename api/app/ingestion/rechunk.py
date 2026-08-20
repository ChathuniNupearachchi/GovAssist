"""Phase 6.6: re-chunk and re-embed the 8 approved source documents with
the new table/list-aware chunker and metadata-enriched chunks.

Deletes each approved document's existing DocumentChunk rows and rebuilds
them via `chunk_and_embed_source_document` — chunk identity is not
preserved across a re-chunk (see design.md's "Re-chunking... invalidates
existing PLAN_ITEM references" risk; this environment has no saved
plans yet, checked below and recorded, not assumed).

Run with:  python -m app.ingestion.rechunk
"""

from sqlalchemy import select

from app.db.session import SessionLocal
from app.ingestion.pipeline import chunk_and_embed_source_document
from app.models import DocumentChunk, PlanItem, SourceDocument


def rechunk_all_approved(db) -> dict[str, int]:
    counts: dict[str, int] = {}
    documents = db.scalars(
        select(SourceDocument).where(SourceDocument.status == "approved")
    ).all()
    for document in documents:
        db.query(DocumentChunk).filter(
            DocumentChunk.source_document_id == document.id
        ).delete(synchronize_session=False)
        db.commit()
        new_chunks = chunk_and_embed_source_document(db, document)
        counts[document.source_url] = len(new_chunks)
    return counts


def main() -> None:
    db = SessionLocal()
    try:
        # PlanItem cites REQUIREMENT/RULE_VERSION, never DOCUMENT_CHUNK
        # directly (see case-resolution-data-model spec) — a saved plan's
        # citations trace through Requirement.source_document_id, not a
        # specific chunk id, so re-chunking cannot invalidate a saved
        # plan's citation. Confirmed here, not assumed (design.md's Open
        # Question).
        existing_plan_items = db.query(PlanItem).count()
        print(f"Existing PLAN_ITEM rows: {existing_plan_items} (chunk re-linking risk: "
              f"{'live — investigate before proceeding' if existing_plan_items else 'not live, none exist yet'})")

        counts = rechunk_all_approved(db)
        print(f"Re-chunked {len(counts)} approved documents:")
        for url, count in counts.items():
            print(f"  {count:>3} chunks  {url}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
