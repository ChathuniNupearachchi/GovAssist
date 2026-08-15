"""Local CPU embedding via sentence-transformers.

Model: all-MiniLM-L6-v2 — 384-dimension output, matching the vector(384)
column Phase 2 already created (see design.md's decision). CPU-only, no
GPU dependency.
"""

from functools import lru_cache

from sentence_transformers import SentenceTransformer

MODEL_NAME = "all-MiniLM-L6-v2"


@lru_cache(maxsize=1)
def get_model() -> SentenceTransformer:
    """Load the embedding model once and cache it for reuse across calls."""
    return SentenceTransformer(MODEL_NAME, device="cpu")


def embed_text(text: str) -> list[float]:
    """Embed a single passage into a 384-dimension vector."""
    model = get_model()
    vector = model.encode(text, convert_to_numpy=True)
    return vector.tolist()
