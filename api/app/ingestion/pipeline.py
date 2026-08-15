"""End-to-end: extract -> chunk -> embed -> persist DocumentChunk rows.

Chunking (chunking.py) and embedding (embedding.py) are separate,
independently testable modules, matching tasks.md's build order. But
DocumentChunk.embedding is NOT NULL (Phase 2 schema) — a chunk is never
persisted without its embedding, so there is no intermediate
"chunked but not yet embedded" row in the database. This function is
where the two steps meet before the single commit.
"""

from sqlalchemy.orm import Session

from app.ingestion.chunking import extract_text, split_into_chunks
from app.ingestion.embedding import embed_text
from app.models import DocumentChunk, SourceDocument


def chunk_and_embed_source_document(
    db: Session, source_document: SourceDocument
) -> list[DocumentChunk]:
    """Extract a source document's text, chunk it, embed each chunk, and
    persist the resulting DocumentChunk rows."""
    text = extract_text(source_document)
    passages = split_into_chunks(text)

    chunks = []
    for sequence, passage in enumerate(passages):
        chunk = DocumentChunk(
            source_document_id=source_document.id,
            chunk_text=passage,
            sequence=sequence,
            embedding=embed_text(passage),
        )
        db.add(chunk)
        chunks.append(chunk)

    db.commit()
    for chunk in chunks:
        db.refresh(chunk)
    return chunks
