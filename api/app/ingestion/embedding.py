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


def with_context_header(
    text: str,
    document_title: str,
    section_heading: str | None,
    source_url: str,
) -> str:
    """Prepend a compact context header to the text that gets EMBEDDED
    (Phase 6.6) — never to the stored, citizen-facing `chunk_text`. A
    chunk of bare table rows or list items is otherwise nearly
    meaningless to a sentence embedding model with no surrounding prose;
    this gives it the document/section/source context a human reader
    gets for free from the page around it.
    """
    header_lines = [f"Document: {document_title}"]
    if section_heading:
        header_lines.append(f"Section: {section_heading}")
    header_lines.append(f"Source: {source_url}")
    return "\n".join(header_lines) + "\n\n" + text
