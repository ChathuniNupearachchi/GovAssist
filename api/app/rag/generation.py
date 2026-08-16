"""5.2 Grounded generation.

Calls the Claude API to answer a citizen's open question using only the
retrieved chunks' text. Never invoked when retrieval found no relevant
match (see `answer.py`) — this module has no "I don't know" branch of
its own because it should never see a weak or empty result in the first
place.

Citations are the chunks passed in, not chunks parsed out of the
generated text: self-check (retrieval.py) already filters to chunks
judged relevant before this function is ever called, so every chunk
handed to `generate_answer` is one the answer may draw from — citing
all of them is simpler and more robust than parsing bracket references
out of freeform model output, and never under- or over-cites relative
to what was actually in the prompt.
"""

from __future__ import annotations

from dataclasses import dataclass

import anthropic

from app.engine.types import Citation
from app.rag.retrieval import RetrievedChunk

MODEL = "claude-opus-5"

SYSTEM_PROMPT = """You answer a Sri Lankan citizen's question about \
Department of Immigration and Emigration passport rules, using ONLY the \
numbered source passages provided in the user message. Do not use any \
knowledge from outside those passages, even if you know the answer.

Write a short, plain-language answer grounded strictly in the passages. \
If the passages do not fully answer the question, say what they do \
cover and note what they do not — never fill the gap from general \
knowledge. Do not produce a document checklist, a fee amount presented \
as authoritative, an office recommendation, or anything that reads like \
a personalized plan — that is the rules engine's job, not yours; you \
are answering a general question about the rules, not resolving a \
citizen's specific case."""


@dataclass(frozen=True)
class RAGAnswer:
    text: str
    citations: list[Citation]


def _build_user_message(query: str, chunks: list[RetrievedChunk]) -> str:
    passages = "\n\n".join(
        f"[{i + 1}] (source: {c.source_document.source_url})\n{c.chunk.chunk_text}"
        for i, c in enumerate(chunks)
    )
    return f"Passages:\n\n{passages}\n\nQuestion: {query}"


def generate_answer(chunks: list[RetrievedChunk], query: str) -> RAGAnswer:
    """Generate a grounded answer from already-retrieved, already-judged-
    relevant chunks. Callers must not invoke this with an empty or weak
    chunk list — see `answer.py`'s "no relevant match" short-circuit."""
    if not chunks:
        raise ValueError(
            "generate_answer requires at least one relevant chunk — "
            "callers must short-circuit to the 'no relevant match' "
            "response before calling this function"
        )

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_user_message(query, chunks)}],
    )

    text = "".join(block.text for block in response.content if block.type == "text")

    citations = [
        Citation(
            source_document_id=c.source_document.id,
            source_url=c.source_document.source_url,
            verified_at=c.source_document.approved_at,
        )
        for c in chunks
    ]
    return RAGAnswer(text=text, citations=citations)
