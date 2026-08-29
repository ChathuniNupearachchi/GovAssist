"""Task 2.4 — unit tests for the reranking stage.

Reranking narrows a candidate pool to the top-k, and the weak-match
check requires the reranker score's own threshold (in addition to the
pre-rerank hybrid signal — see design.md's "AND, not a replacement"
decision) rather than raw cosine/RRF alone.
"""

from __future__ import annotations

from app.rag.retrieval import _RERANK_THRESHOLD, _is_strong_match, _search_reranked
from app.rag.rerank import Scored, rerank


def test_reranking_narrows_a_candidate_pool_to_top_k(db):
    chunks, hybrid_ok = _search_reranked(
        db, "What is the fee for a name change amendment?", top_k=3, pool_size=10
    )
    assert len(chunks) <= 3
    assert all(c.rerank_score is not None for c in chunks)
    # Best rerank score first.
    scores = [c.rerank_score for c in chunks]
    assert scores == sorted(scores, reverse=True)


def test_rerank_scores_every_candidate_against_the_query():
    candidates = ["An authorised photo studio is one designated by the Department.", "The weather is sunny."]
    scored = rerank(
        "What is an authorised photo studio?", candidates, text_of=lambda c: c, top_k=2
    )
    assert len(scored) == 2
    assert all(isinstance(s, Scored) for s in scored)
    # The relevant passage should score higher than the irrelevant one.
    assert scored[0].item == candidates[0]


def test_weak_match_check_requires_rerank_score_not_raw_cosine_rrf():
    from app.rag.retrieval import RetrievedChunk

    # ms-marco-MiniLM-L-6-v2 returns raw, unbounded logits (confirmed
    # directly: a relevant pair ~3.0, an irrelevant pair ~-11.3) — not a
    # [0, 1] sigmoid scale, so these fixtures use values on that scale.

    # Hybrid signal accepts (agreement above the single-signal floor),
    # but the reranker score itself is below threshold — SHALL reject,
    # not fall back to the raw hybrid/cosine signal alone.
    strong_hybrid_weak_rerank = RetrievedChunk(
        chunk=None, source_document=None, score=0.05, vector_distance=0.2, rerank_score=-10.0
    )
    assert _is_strong_match([strong_hybrid_weak_rerank], hybrid_ok=True) is False
    assert strong_hybrid_weak_rerank.rerank_score < _RERANK_THRESHOLD

    # Reranker score clears the threshold, but the hybrid signal itself
    # did not accept — SHALL still reject (an AND, not a reranker-only
    # decision).
    weak_hybrid_strong_rerank = RetrievedChunk(
        chunk=None, source_document=None, score=0.0, vector_distance=0.9, rerank_score=3.0
    )
    assert _is_strong_match([weak_hybrid_strong_rerank], hybrid_ok=False) is False

    # Both signals agree — accepted.
    both_agree = RetrievedChunk(
        chunk=None, source_document=None, score=0.05, vector_distance=0.2, rerank_score=3.0
    )
    assert _is_strong_match([both_agree], hybrid_ok=True) is True
