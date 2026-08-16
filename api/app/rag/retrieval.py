"""5.1 Retrieval + 5.3 Retrieval self-check.

Embeds a query with the same model used at ingestion, searches
DOCUMENT_CHUNK via pgvector cosine distance, and scopes strictly to
chunks whose SourceDocument.status is 'approved'. The self-check is a
pure cosine-distance threshold (no extra Claude API call — see design.md's
Context: this stays within CLAUDE.md's four authorized narrow Claude API
jobs rather than adding a fifth). A weak top match triggers one
non-LLM query reformulation and one retry before giving up.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingestion.embedding import embed_text
from app.models import DocumentChunk, SourceDocument

# Calibrated against the real re-embedded corpus (post-boilerplate-strip;
# measured, not estimated — see tasks.md 4.2 for the full record):
#   "What is an authorised photo studio?"             -> top distance 0.7152 (pages_e.php?id=7, correct)
#   "What is the fee for a name change amendment?"    -> top distance 0.5174 (pages_e.php?id=10, correct)
#   "What is the weather forecast for Paris tomorrow?" (absent topic)
#                                                      -> top distance 0.9681
# 0.78 clears both required positive queries with margin and still
# rejects the absent-topic query. Known limitation, not papered over:
# a genuinely in-corpus query with different phrasing from the source
# text ("What are the working hours at the Head Office?", covered by
# id=7) scored 0.8311 — above this threshold — so some real, answerable
# questions will still fall through to "no relevant match" on this small
# 8-document corpus with this embedding model. Documented as a risk in
# design.md rather than hidden by a looser threshold that would instead
# start accepting topically-adjacent-but-uncovered queries (e.g. "driving
# license", measured at 0.7358, well inside a looser threshold despite
# not being immigration-passport content at all).
WEAK_MATCH_THRESHOLD = 0.78

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
    distance: float  # cosine distance — lower is more similar


@dataclass(frozen=True)
class RetrievalResult:
    chunks: list[RetrievedChunk]
    relevant: bool  # False = "no relevant match" — never pass to generation


def _search(db: Session, query: str, top_k: int) -> list[RetrievedChunk]:
    query_vector = embed_text(query)
    rows = db.execute(
        select(
            DocumentChunk,
            SourceDocument,
            DocumentChunk.embedding.cosine_distance(query_vector).label("distance"),
        )
        .join(SourceDocument, DocumentChunk.source_document_id == SourceDocument.id)
        .where(SourceDocument.status == "approved")
        .order_by("distance")
        .limit(top_k)
    ).all()
    return [
        RetrievedChunk(chunk=chunk, source_document=doc, distance=distance)
        for chunk, doc, distance in rows
    ]


def _reformulate(query: str) -> str:
    keywords = [
        word for word in query.strip("?.! ").split()
        if word.lower() not in _STOPWORDS
    ]
    return " ".join(keywords) if keywords else query


def retrieve(db: Session, query: str, top_k: int = 5) -> RetrievalResult:
    """Retrieve the top matching approved chunks for a query, with one
    reformulation retry on a weak initial match."""
    chunks = _search(db, query, top_k)
    if chunks and chunks[0].distance <= WEAK_MATCH_THRESHOLD:
        return RetrievalResult(chunks=chunks, relevant=True)

    reformulated = _reformulate(query)
    retry_chunks = _search(db, reformulated, top_k) if reformulated != query else chunks
    if retry_chunks and retry_chunks[0].distance <= WEAK_MATCH_THRESHOLD:
        return RetrievalResult(chunks=retry_chunks, relevant=True)

    return RetrievalResult(chunks=[], relevant=False)
