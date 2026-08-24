"""2. RERANKER — `cross-encoder/ms-marco-MiniLM-L-6-v2`, self-hosted, CPU.

A cross-encoder that scores a (query, passage) pair jointly, rather than
comparing separately-embedded vectors — the standard second stage after
a wider, cheaper first-stage retrieval (here: the existing hybrid
vector + full-text + identifier search), narrowing a broader candidate
pool down to the few passages actually worth generating from. Loaded
once and cached, matching `app.ingestion.embedding`'s pattern.

Originally `BAAI/bge-reranker-base` (278M params, sigmoid-activated
scores in [0, 1]) — swapped to this ~22M-param model after `bge-
reranker-base` measured ~13 seconds per query on this machine's 2-core
CPU, an unacceptable citizen-facing latency (see design.md's Decision).
This model's `CrossEncoder.predict()` returns raw, unbounded logits (a
clearly relevant pair scored ~3.0, a clearly irrelevant pair ~-11.3,
confirmed directly) — not a [0, 1] sigmoid scale like the previous
model, so `retrieval.py`'s `_RERANK_THRESHOLD` is calibrated on a
different, negative-inclusive scale. See design.md's calibration table
for the measured evidence for both models.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Generic, TypeVar

from sentence_transformers import CrossEncoder

MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"

T = TypeVar("T")


@lru_cache(maxsize=1)
def get_model() -> CrossEncoder:
    """Load the reranker model once and cache it for reuse across calls."""
    return CrossEncoder(MODEL_NAME, device="cpu")


@dataclass(frozen=True)
class Scored(Generic[T]):
    item: T
    rerank_score: float


def rerank(query: str, candidates: list[T], text_of: "callable[[T], str]", top_k: int) -> list[Scored[T]]:
    """Scores every candidate against `query` and returns the top `top_k`,
    best first. `text_of` extracts the passage text to score from each
    candidate — kept generic rather than importing `RetrievedChunk`
    directly, so this module stays reusable if reranking is ever needed
    for something other than a `DocumentChunk`."""
    if not candidates:
        return []
    model = get_model()
    pairs = [(query, text_of(c)) for c in candidates]
    scores = model.predict(pairs)
    scored = sorted(
        (Scored(item=c, rerank_score=float(s)) for c, s in zip(candidates, scores)),
        key=lambda s: s.rerank_score,
        reverse=True,
    )
    return scored[:top_k]
