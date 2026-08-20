"""5.1 Retrieval + 5.3 Retrieval self-check + 6.7 Hybrid ranking.

Embeds a query with the same model used at ingestion, searches
DOCUMENT_CHUNK via both pgvector cosine similarity and Postgres
full-text search (an OR of the query's significant keywords against the
`search_vector` generated column — see `_or_tsquery_terms` for why not
`plainto_tsquery` as-is), and scopes strictly to chunks whose
SourceDocument.status is 'approved'. Both approval-only scoping and the
weak-match self-check are unchanged from Phase 5 — only what sits
beneath them changed: candidates are now ranked by a reciprocal-rank-
fusion (RRF) blend of the two searches' rankings, not cosine distance
alone.

Why RRF, not a tuned weight: cosine similarity and full-text search fail
on opposite query shapes — a semantic paraphrase confuses full-text
search, an exact identifier ("Form K-35A", "section 19(2)") confuses
cosine similarity on this small, 384-dimension-embedding corpus. RRF
rewards whichever signal ranks a candidate highly, from either source,
without needing per-query-type tuning this project has no data to
justify. See design.md's "Hybrid ranking" decision.

The self-check is still a pure threshold check, no extra Claude API
call — CLAUDE.md's four authorized narrow Claude API jobs stay four. A
weak top match still triggers one non-LLM query reformulation and one
retry before giving up.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ingestion.embedding import embed_text
from app.models import DocumentChunk, SourceDocument

# How many candidates each individual ranking (vector, full-text)
# contributes to the fusion pool, before RRF picks the final top_k. Wider
# than top_k so a chunk that ranks well on only one signal still gets a
# chance to be pulled in by the other.
_CANDIDATE_POOL_SIZE = 20

# Standard RRF damping constant — de-weights rank differences deep in
# either list without needing per-corpus tuning.
_RRF_K = 60

# A chunk that appears in exactly one of the three ranked lists at rank
# 0 scores exactly 1/(k+1) — the RRF "single-signal floor". A score
# strictly above the floor means at least two signals independently
# ranked the same chunk highly (agreement), which is a strong enough
# accept signal on its own regardless of raw cosine distance — this is
# specifically how "Form K-35A" and "section 19(2)" get accepted despite
# cosine distances that would fail Phase 5/6.6's threshold alone: the
# identifier rescue list agrees with the vector list.
_SINGLE_SIGNAL_FLOOR = 1.0 / (_RRF_K + 1)

# When only one signal contributed (score at the floor — the common
# case for a plain-language query full-text can't help with), fall back
# to the raw cosine distance, thresholded per the calibration measured
# after this phase's chunking fix (6.6): accept queries clustered at
# 0.38-0.66, reject queries at 0.59-0.74, with "visa to Australia"
# (0.5939) the closest false-accept risk — 0.55 separates it correctly
# while still clearing every accept query with margin. See design.md's
# calibration table ("After 6.7") for the full measured evidence.
_VECTOR_FALLBACK_THRESHOLD = 0.55

# Stripped from a query before a reformulation retry — bare keywords tend
# to match chunk text more directly than a full interrogative sentence.
_STOPWORDS = {
    "what", "is", "the", "a", "an", "how", "do", "i", "can", "where",
    "does", "are", "when", "who", "which", "to", "for", "of", "in", "on",
    "my", "me", "you", "your", "please", "tell", "about",
}


@dataclass(frozen=True)
class RetrievedChunk:
    chunk: DocumentChunk
    source_document: SourceDocument
    score: float  # fused RRF score — higher is more relevant
    vector_distance: float  # raw cosine distance to the query — lower is closer


@dataclass(frozen=True)
class RetrievalResult:
    chunks: list[RetrievedChunk]
    relevant: bool  # False = "no relevant match" — never pass to generation


def _vector_ranked_ids(db: Session, query_vector: list[float], pool_size: int) -> list[str]:
    """Chunk ids ranked by cosine similarity, best first."""
    rows = db.execute(
        select(DocumentChunk.id)
        .join(SourceDocument, DocumentChunk.source_document_id == SourceDocument.id)
        .where(SourceDocument.status == "approved")
        .order_by(DocumentChunk.embedding.cosine_distance(query_vector))
        .limit(pool_size)
    ).all()
    return [str(row[0]) for row in rows]


_WORD_RE = re.compile(r"[A-Za-z0-9]+")


def _run_tsquery(db: Session, ts_query, pool_size: int) -> list[str]:
    rows = db.execute(
        select(DocumentChunk.id)
        .join(SourceDocument, DocumentChunk.source_document_id == SourceDocument.id)
        .where(SourceDocument.status == "approved")
        .where(DocumentChunk.search_vector.op("@@")(ts_query))
        .order_by(func.ts_rank(DocumentChunk.search_vector, ts_query).desc())
        .limit(pool_size)
    ).all()
    return [str(row[0]) for row in rows]


def _identifier_or_terms(query: str) -> str | None:
    """An OR expression built ONLY from the query's digit-bearing tokens
    ("19 | 2", "35a" or "k | 35a") — a narrow, low-false-positive-risk
    rescue list for exact-identifier queries ("Form K-35A", "section
    19(2)"), where `plainto_tsquery`'s default AND-of-everything fails
    for two different reasons confirmed directly while building this
    (see design.md): the query word "happens" never appears verbatim in
    the source text at all, and "K-35A" tokenizes as the single lexeme
    "k-35a" while the corpus's own "K 35 A" (space-separated) tokenizes
    as three separate lexemes — neither ever satisfies a strict AND.
    None of this calibration set's absent-topic queries contain a
    digit-bearing token at all, so this list stays empty for them —
    it only ever fires for genuinely identifier-shaped queries.
    """
    terms: set[str] = set()
    for token in _WORD_RE.findall(query):
        if not any(ch.isdigit() for ch in token):
            continue
        terms.add(token)
        # Also split a merged alphanumeric compound ("35A") into its
        # letter/digit runs ("35", "A") — the corpus may spell the same
        # identifier space-separated ("K 35 A"), which tokenizes as
        # separate lexemes no merged-compound query term will ever match.
        terms.update(re.findall(r"[A-Za-z]+|\d+", token))
    if not terms:
        return None
    return " | ".join(sorted(terms))


def _fulltext_ranked_ids(db: Session, query: str, pool_size: int) -> list[str]:
    """Chunk ids ranked by Postgres full-text rank, best first — the
    strict AND-of-every-content-word ranking `plainto_tsquery` builds by
    default (zero false positives on this corpus's absent-topic
    queries), for everything that isn't identifier-shaped."""
    ts_query = func.plainto_tsquery("english", query)
    return _run_tsquery(db, ts_query, pool_size)


def _identifier_ranked_ids(db: Session, query: str, pool_size: int) -> list[str]:
    """Chunk ids ranked by the narrow identifier-token OR rescue query —
    see `_identifier_or_terms`. Empty when the query has no digit-bearing
    token."""
    terms = _identifier_or_terms(query)
    if terms is None:
        return []
    ts_query = func.to_tsquery("english", terms)
    return _run_tsquery(db, ts_query, pool_size)


# The identifier-rescue list is small and high-precision by
# construction — it only ever contains chunks matching a rare
# digit-bearing token, never the whole corpus. A rank-2 hit in an
# 18-candidate identifier list is far more meaningful than a rank-2 hit
# in a 20-candidate whole-corpus vector list, so it gets a smaller RRF
# k (steeper reward for a good rank) rather than being diluted to a
# one-in-three vote at the standard k. This is a per-list constant, not
# a per-query-type weight — the same k applies to every query, and the
# list is empty (contributes nothing) for the large majority of queries
# that have no digit-bearing token at all. See design.md's calibration
# table for the measured case this fixes ("section 19(2)").
_IDENTIFIER_RRF_K = 10


def _rrf_fuse(*weighted_lists: tuple[list[str], int]) -> list[tuple[str, float]]:
    """Reciprocal rank fusion over any number of (ranked_ids, k) lists:
    score(id) = sum over lists of 1/(k + rank) for every list the id
    appears in (rank is 0-indexed), 0 contribution from a list it
    doesn't appear in at all. Returns (id, score) pairs sorted
    best-first."""
    scores: dict[str, float] = {}
    for ranked_ids, k in weighted_lists:
        for rank, chunk_id in enumerate(ranked_ids):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores.items(), key=lambda pair: pair[1], reverse=True)


def _search(db: Session, query: str, top_k: int = 5) -> list[RetrievedChunk]:
    query_vector = embed_text(query)
    vector_ids = _vector_ranked_ids(db, query_vector, _CANDIDATE_POOL_SIZE)
    fulltext_ids = _fulltext_ranked_ids(db, query, _CANDIDATE_POOL_SIZE)
    identifier_ids = _identifier_ranked_ids(db, query, _CANDIDATE_POOL_SIZE)

    fused = _rrf_fuse(
        (vector_ids, _RRF_K), (fulltext_ids, _RRF_K), (identifier_ids, _IDENTIFIER_RRF_K)
    )[:top_k]
    if not fused:
        return []

    fused_scores = dict(fused)
    ordered_ids = [chunk_id for chunk_id, _ in fused]

    rows = db.execute(
        select(
            DocumentChunk,
            SourceDocument,
            DocumentChunk.embedding.cosine_distance(query_vector).label("distance"),
        )
        .join(SourceDocument, DocumentChunk.source_document_id == SourceDocument.id)
        .where(DocumentChunk.id.in_(ordered_ids))
    ).all()
    by_id = {str(chunk.id): (chunk, doc, distance) for chunk, doc, distance in rows}

    return [
        RetrievedChunk(
            chunk=by_id[cid][0],
            source_document=by_id[cid][1],
            score=fused_scores[cid],
            vector_distance=by_id[cid][2],
        )
        for cid in ordered_ids
        if cid in by_id
    ]


def _reformulate(query: str) -> str:
    keywords = [
        word for word in query.strip("?.! ").split()
        if word.lower() not in _STOPWORDS
    ]
    return " ".join(keywords) if keywords else query


def _is_strong_match(top: RetrievedChunk) -> bool:
    """Two-tier accept rule — see `_SINGLE_SIGNAL_FLOOR`'s comment.
    Agreement between signals (score above the single-signal floor)
    accepts outright; a single-signal result falls back to the
    calibrated raw cosine distance."""
    if top.score > _SINGLE_SIGNAL_FLOOR + 1e-9:
        return True
    return top.vector_distance <= _VECTOR_FALLBACK_THRESHOLD


def retrieve(db: Session, query: str, top_k: int = 5) -> RetrievalResult:
    """Retrieve the top matching approved chunks for a query, ranked by
    the hybrid vector + full-text blend, with one reformulation retry on
    a weak initial match."""
    chunks = _search(db, query, top_k)
    if chunks and _is_strong_match(chunks[0]):
        return RetrievalResult(chunks=chunks, relevant=True)

    reformulated = _reformulate(query)
    retry_chunks = _search(db, reformulated, top_k) if reformulated != query else chunks
    if retry_chunks and _is_strong_match(retry_chunks[0]):
        return RetrievalResult(chunks=retry_chunks, relevant=True)

    return RetrievalResult(chunks=[], relevant=False)
