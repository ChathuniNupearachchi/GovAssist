"""4.4 Retrieval unit tests: approved-only scoping, weak-match retry,
still-weak-after-retry. Updated for 6.7's hybrid ranking — `_search`
now returns a fused RRF score (higher is more relevant) plus the raw
cosine distance, not a cosine distance alone; see
`app/rag/retrieval.py`'s module docstring."""

import uuid
from datetime import datetime, timezone

from app.ingestion.embedding import embed_text
from app.models import DocumentChunk, SourceDocument
from app.rag.retrieval import _search, retrieve


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
    # RERANK_ENABLED defaults to False (measured decision — reranking
    # changes zero accept/reject outcomes on this project's calibration
    # set while costing ~2.2s/query; see retrieval.py's RERANK_ENABLED
    # comment), so this is the hybrid-only path: the returned top
    # chunk's raw `vector_distance` is exactly what `_hybrid_accept`
    # gated on.
    result = retrieve(db, "What is an authorised photo studio?")
    assert result.relevant is True
    assert result.chunks
    assert result.chunks[0].vector_distance <= 0.55
    assert result.chunks[0].rerank_score is None


def test_strong_match_with_reranking_enabled(db, monkeypatch):
    import app.rag.retrieval as retrieval_module

    monkeypatch.setattr(retrieval_module, "RERANK_ENABLED", True)
    result = retrieve(db, "What is an authorised photo studio?")
    assert result.relevant is True
    assert result.chunks
    # Since Step 2 (reranker): the returned top chunk is `retrieve()`'s
    # reranked top-1, which reranking can legitimately promote over
    # hybrid search's own top pick — its raw `vector_distance` is no
    # longer what the accept/reject decision gates on (that's the hybrid
    # pool's own top-1, evaluated separately inside `_search_reranked`;
    # see `retrieval.py`'s `_hybrid_accept`/`_is_strong_match`), so
    # asserting a distance threshold directly on the returned chunk no
    # longer reflects why this query is accepted. `rerank_score` is what
    # the reranked path now surfaces on the returned chunk instead.
    assert result.chunks[0].rerank_score is not None
    # ms-marco-MiniLM-L-6-v2's raw logit scale (see rerank.py) — the
    # calibrated floor (_RERANK_THRESHOLD), not a [0, 1] sigmoid bound.
    assert result.chunks[0].rerank_score >= -5.0


def test_exact_identifier_query_returns_relevant_result(db):
    # "Form K-35A" fails a cosine-only threshold on its own (the corpus
    # spells it "K 35 A", space-separated — the embedding model doesn't
    # treat that as a close paraphrase of "K-35A"). Hybrid ranking
    # accepts it via multi-signal agreement: the identifier-rescue
    # full-text list independently ranks the same chunk highly. See
    # design.md's calibration table.
    result = retrieve(db, "What is Form K-35A?")
    assert result.relevant is True
    assert result.chunks


def test_absent_topic_triggers_retry_then_no_relevant_match(db):
    result = retrieve(db, "What is the weather forecast for Paris tomorrow?")
    assert result.relevant is False
    assert result.chunks == []


def test_absent_topic_with_no_digit_token_never_gets_identifier_rescue(db):
    # None of these reject queries contain a digit-bearing token, so the
    # identifier-rescue list (6.7) is empty for all of them — confirms
    # the rescue mechanism built for exact identifiers doesn't
    # accidentally reintroduce a false accept for a plain-language,
    # topically-absent query.
    for query in [
        "How do I renew my driving license?",
        "What is the weather in Colombo?",
        "How do I apply for a visa to Australia?",
    ]:
        result = retrieve(db, query)
        assert result.relevant is False, f"expected no relevant match for: {query}"
