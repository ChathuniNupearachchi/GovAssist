"""End-to-end: extract -> chunk -> embed -> persist DocumentChunk rows.

Extraction now produces structured blocks (Phase 6.6), chunking groups
them into prose/table/list chunks, and embedding still operates on plain
text — but the text handed to `embed_text` is the header-prefixed
representation (`with_context_header`), while `DocumentChunk.chunk_text`
stores the raw chunk content only. See document-chunking spec's "Only
the embedded representation carries the context header" requirement.

DocumentChunk.embedding is NOT NULL (Phase 2 schema) — a chunk is never
persisted without its embedding, so there is no intermediate
"chunked but not yet embedded" row in the database.
"""

from sqlalchemy.orm import Session

from app.ingestion.blocks import document_title
from app.ingestion.chunking import build_chunks, extract_blocks
from app.ingestion.embedding import embed_text, with_context_header
from app.models import DocumentChunk, SourceDocument


def chunk_and_embed_source_document(
    db: Session, source_document: SourceDocument
) -> list[DocumentChunk]:
    """Extract a source document's structured blocks, chunk them, embed
    each chunk's header-prefixed text, and persist the resulting
    DocumentChunk rows."""
    blocks = extract_blocks(source_document)
    passages = build_chunks(blocks)
    title = document_title(source_document)

    chunks = []
    for sequence, passage in enumerate(passages):
        embed_input = with_context_header(
            passage.text, title, passage.section_heading, source_document.source_url
        )
        chunk = DocumentChunk(
            source_document_id=source_document.id,
            chunk_text=passage.text,
            sequence=sequence,
            embedding=embed_text(embed_input),
            chunk_metadata={
                "document_title": title,
                "section_heading": passage.section_heading,
                "content_type": passage.content_type,
                "source_url": source_document.source_url,
            },
        )
        db.add(chunk)
        chunks.append(chunk)

    db.commit()
    for chunk in chunks:
        db.refresh(chunk)
    return chunks
