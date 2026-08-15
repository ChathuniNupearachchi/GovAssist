"""Word-count based chunking: ~200-400 words per chunk, preferring
paragraph boundaries over a hard mid-sentence cut (see design.md)."""

from app.ingestion.html_extraction import extract_html_text
from app.ingestion.pdf_extraction import extract_pdf_text
from app.models import SourceDocument

MIN_CHUNK_WORDS = 200
MAX_CHUNK_WORDS = 400


def extract_text(source_document: SourceDocument) -> str:
    """Extract a source document's text, dispatching on its document_type."""
    if source_document.document_type == "pdf":
        return extract_pdf_text(source_document)
    return extract_html_text(source_document)


def split_into_chunks(
    text: str,
    min_words: int = MIN_CHUNK_WORDS,
    max_words: int = MAX_CHUNK_WORDS,
) -> list[str]:
    """Split text into ~200-400 word passages, in source order.

    Prefers to close a chunk at a paragraph boundary once it's within
    range; only hard-splits mid-paragraph when a single paragraph alone
    exceeds max_words.
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs and text.strip():
        paragraphs = [text.strip()]

    chunks: list[str] = []
    current_words: list[str] = []

    for paragraph in paragraphs:
        paragraph_words = paragraph.split()

        if current_words and len(current_words) + len(paragraph_words) > max_words:
            chunks.append(" ".join(current_words))
            current_words = []

        current_words.extend(paragraph_words)

        while len(current_words) > max_words:
            chunks.append(" ".join(current_words[:max_words]))
            current_words = current_words[max_words:]

        if len(current_words) >= min_words:
            chunks.append(" ".join(current_words))
            current_words = []

    if current_words:
        fits_in_previous = (
            chunks
            and len(current_words) < min_words
            and len(chunks[-1].split()) + len(current_words) <= max_words
        )
        if fits_in_previous:
            # Too small to stand alone, and merging keeps the previous
            # chunk within max_words — fold in rather than leaving an
            # undersized trailing chunk.
            chunks[-1] = chunks[-1] + " " + " ".join(current_words)
        else:
            chunks.append(" ".join(current_words))

    return chunks
