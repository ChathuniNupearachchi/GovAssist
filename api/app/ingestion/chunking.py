"""Block-aware chunking — Phase 6.6.

Prose text is still split on ~200-400 word boundaries, preferring
paragraph breaks (unchanged from Phase 3). Table and list blocks are
never split — each becomes exactly one chunk, however many words it
contains, because splitting a fee table loses the header row that makes
its numbers mean anything (see design.md).

A chunk carries its own `content_type` and `section_heading`, populated
from the block(s) it was built from. A run of consecutive prose blocks
is joined (blank-line separated) before word-count chunking runs over
it, so prose chunking behaves exactly as it did pre-6.6, just fed one
paragraph-run at a time instead of the whole document at once — the
only behavioral difference is that a table/list block now interrupts a
prose run instead of being flattened into it.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.ingestion.blocks import ExtractedBlock
from app.ingestion.html_extraction import extract_html_blocks
from app.ingestion.pdf_extraction import extract_pdf_blocks
from app.models import SourceDocument

MIN_CHUNK_WORDS = 200
MAX_CHUNK_WORDS = 400

# A prose run this short, standing alone between two table/list blocks
# (or at a document's start/interior), is a trailing FAQ-style question
# whose actual answer is the block that follows it, not real standalone
# content — confirmed directly against pages_e.php?id=8's "Issue of
# Passports" page, where at least 5 chunks were nothing but a bare
# question ("Where can I obtain an application form ?", 7 words) split
# off from the list that answers it. Below this threshold, the fragment
# is held and merged as a prefix into the following block instead of
# becoming its own near-content-free chunk (langgraph-orchestration-
# branch design.md's "reranker false-accept" finding — discovered
# because bge-reranker-base scores a bare question against any
# similarly-phrased query, with no real content to disambiguate against,
# in a way hybrid RRF search's full-text/cosine weighting didn't
# surface).
_MIN_STANDALONE_PROSE_WORDS = 12


@dataclass(frozen=True)
class Chunk:
    text: str
    content_type: str  # "prose" | "table" | "list"
    section_heading: str | None


def extract_blocks(source_document: SourceDocument) -> list[ExtractedBlock]:
    """Extract a source document's structured blocks, dispatching on its
    document_type."""
    if source_document.document_type == "pdf":
        return extract_pdf_blocks(source_document)
    return extract_html_blocks(source_document)


def split_into_chunks(
    text: str,
    min_words: int = MIN_CHUNK_WORDS,
    max_words: int = MAX_CHUNK_WORDS,
) -> list[str]:
    """Split prose text into ~200-400 word passages, in source order.

    Prefers to close a chunk at a paragraph boundary once it's within
    range; only hard-splits mid-paragraph when a single paragraph alone
    exceeds max_words. Unchanged from Phase 3 — table/list blocks never
    reach this function; see `build_chunks`.
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


def build_chunks(
    blocks: list[ExtractedBlock],
    min_words: int = MIN_CHUNK_WORDS,
    max_words: int = MAX_CHUNK_WORDS,
) -> list[Chunk]:
    """Turn a document's ordered blocks into chunks.

    A run of consecutive prose blocks is merged and passed through the
    unchanged word-count chunker; the resulting chunks are tagged with
    the section heading in effect at the start of the run (a run rarely
    spans more than one heading in this corpus, and this is an accepted
    approximation for the case where it does — see design.md). Each
    table or list block becomes exactly one chunk on its own, whatever
    its word count.
    """
    chunks: list[Chunk] = []
    prose_run: list[str] = []
    run_heading: str | None = None
    # An undersized trailing prose fragment, held until the next block
    # is known, so it can be merged as that block's prefix rather than
    # emitted as its own near-content-free chunk — see
    # `_MIN_STANDALONE_PROSE_WORDS`'s comment.
    pending_prefix: str | None = None

    def flush_prose_run() -> None:
        nonlocal pending_prefix
        if not prose_run:
            return
        merged = "\n\n".join(prose_run)
        passages = split_into_chunks(merged, min_words, max_words)
        prose_run.clear()
        if len(passages) == 1 and len(passages[0].split()) < _MIN_STANDALONE_PROSE_WORDS:
            pending_prefix = passages[0]
            return
        for passage in passages:
            chunks.append(Chunk(text=passage, content_type="prose", section_heading=run_heading))

    for block in blocks:
        if block.content_type == "prose":
            if not prose_run:
                run_heading = block.section_heading
            prose_run.append(block.text)
            continue

        # A table or list block interrupts the current prose run and
        # becomes its own chunk, never split regardless of word count —
        # except an undersized trailing prose fragment immediately
        # preceding it is prepended rather than dropped or left standing
        # alone.
        flush_prose_run()
        text = block.text
        if pending_prefix is not None:
            text = pending_prefix + "\n\n" + text
            pending_prefix = None
        chunks.append(Chunk(text=text, content_type=block.content_type, section_heading=block.section_heading))

    flush_prose_run()
    if pending_prefix is not None:
        # The document ended on an undersized trailing fragment with no
        # following block to merge into — emit it standalone rather than
        # silently dropping citizen-relevant text.
        chunks.append(Chunk(text=pending_prefix, content_type="prose", section_heading=run_heading))

    return chunks
