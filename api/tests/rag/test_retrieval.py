"""4.4 Retrieval unit tests: approved-only scoping, weak-match retry,
still-weak-after-retry."""

import uuid
from datetime import datetime, timezone

from app.ingestion.embedding import embed_text
from app.models import DocumentChunk, SourceDocument
from app.rag.retrieval import WEAK_MATCH_THRESHOLD, _search, retrieve


def test_approved_only_scoping_excludes_pending_documents(db):
    # None of the real ingested documents happen to have a pending
    # SourceDocument with chunks (Phase 3/5 only ever chunked the
    # first-fetch, now-approved rows), so this test builds a controlled
    # case: a pending document whose one chunk is embedded to be an
    # unmistakably strong match for the query, then confirms it is
    # excluded anyway. Cleaned up in a finally block, not left behind.
    query = "What is an authorised photo studio?"
    pending_doc = SourceDocument(
        id=uuid.uuid4(),
        source_url="https://example.invalid/pending-test-doc",
        content_hash="test",
        document_type="html",
        fetched_at=datetime.now(timezone.utc),
        status="pending",
    )
    db.add(pending_doc)
    db.flush()
    pending_chunk = DocumentChunk(
        id=uuid.uuid4(),
        source_document_id=pending_doc.id,
        chunk_text=query,  # embedding this exact query text: distance ~0
        sequence=0,
        embedding=embed_text(query),
    )
    db.add(pending_chunk)
    db.commit()

    try:
        results = _search(db, query, top_k=50)
        assert not any(r.chunk.id == pending_chunk.id for r in results), (
            "a chunk belonging to a pending document was returned by "
            "retrieval, even though it was the closest possible match"
        )
    finally:
        db.delete(pending_chunk)
        db.delete(pending_doc)
        db.commit()


def test_strong_match_returns_relevant_result(db):
    result = retrieve(db, "What is an authorised photo studio?")
    assert result.relevant is True
    assert result.chunks
    assert result.chunks[0].distance <= WEAK_MATCH_THRESHOLD


def test_absent_topic_triggers_retry_then_no_relevant_match(db):
    result = retrieve(db, "What is the weather forecast for Paris tomorrow?")
    assert result.relevant is False
    assert result.chunks == []
