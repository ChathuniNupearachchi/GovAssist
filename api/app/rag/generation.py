"""5.2 Grounded generation + 6.9 Citation verification.

Calls the Claude API to answer a citizen's open question using only the
retrieved chunks' text. Never invoked when retrieval found no relevant
match (see `answer.py`) — this module has no "I don't know" branch of
its own for a weak/empty retrieval result; it does have one for a
generation call that fails citation verification twice (see below).

Phase 5 originally cited every chunk passed in, unconditionally — simple
and impossible to under-cite, but also impossible to catch a model that
fabricates a source it was never given, since nothing checked what the
model actually did against what it was actually given. Phase 6.9 closes
that gap: generation is forced into a structured schema
(`client.messages.parse`, the same structured-output path
`app.chat.classifier` already uses) naming which chunk id(s) the answer
actually draws from, and every cited id is verified to be a member of
the retrieved set before the answer is trusted. A citation outside that
set, or no citation at all, is rejected and retried once with an
explicit instruction; a second failure returns `None`, and `answer.py`
falls back to the same explicit "no relevant match" response weak
retrieval already produces — one consistent failure mode, not two.

This is a set-membership check against data already in memory — zero
additional Claude API calls, zero added runtime cost on the success
path.
"""

from __future__ import annotations

from dataclasses import dataclass

import anthropic
from pydantic import BaseModel

from app.engine.types import Citation
from app.rag.retrieval import RetrievedChunk

MODEL = "claude-sonnet-5"

SYSTEM_PROMPT = """You answer a Sri Lankan citizen's question about \
Department of Immigration and Emigration passport rules, using ONLY the \
source passages provided in the user message. Do not use any knowledge \
from outside those passages, even if you know the answer.

Write a short, plain-language answer grounded strictly in the passages. \
If the passages do not fully answer the question, say what they do \
cover and note what they do not — never fill the gap from general \
knowledge. Do not produce a document checklist, a fee amount presented \
as authoritative, an office recommendation, or anything that reads like \
a personalized plan — that is the rules engine's job, not yours; you \
are answering a general question about the rules, not resolving a \
citizen's specific case.

For every passage your answer actually draws from, cite it: report its \
exact chunk_id (given before each passage) and a short quoted_span from \
that passage supporting your answer. Cite only passages you actually \
used — never a chunk_id that wasn't given to you, and never leave \
citations empty if your answer states anything from the passages."""

RETRY_INSTRUCTION = """

Your previous answer either cited a chunk_id that was not among the \
passages given to you, or cited none at all. Answer again, using ONLY \
the exact chunk_id values given before each passage below, and cite at \
least one."""


class GenerationCitation(BaseModel):
    chunk_id: str
    quoted_span: str


class StructuredAnswer(BaseModel):
    answer: str
    citations: list[GenerationCitation]


@dataclass(frozen=True)
class RAGAnswer:
    text: str
    citations: list[Citation]
    cited_chunk_ids: list[str]  # 6.10: the audit trail on CHAT_MESSAGE reads this


def _build_user_message(query: str, chunks: list[RetrievedChunk]) -> str:
    passages = "\n\n".join(
        f"[chunk_id: {c.chunk.id}] (source: {c.source_document.source_url})\n{c.chunk.chunk_text}"
        for c in chunks
    )
    return f"Passages:\n\n{passages}\n\nQuestion: {query}"


def _verify(parsed: StructuredAnswer, retrieved_ids: set[str]) -> bool:
    """A grounded answer always has at least one citation, and every
    cited chunk_id must be a member of the retrieved set — see
    rag-answering spec's "Generation answers only from retrieved chunks
    and always cites them" (MODIFIED, 6.9)."""
    if not parsed.citations:
        return False
    cited_ids = {c.chunk_id for c in parsed.citations}
    return cited_ids.issubset(retrieved_ids)


def _call_model(query: str, chunks: list[RetrievedChunk], retry: bool) -> StructuredAnswer:
    client = anthropic.Anthropic()
    system = SYSTEM_PROMPT + (RETRY_INSTRUCTION if retry else "")
    response = client.messages.parse(
        model=MODEL,
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": _build_user_message(query, chunks)}],
        output_format=StructuredAnswer,
    )
    return response.parsed_output


def generate_answer(chunks: list[RetrievedChunk], query: str) -> RAGAnswer | None:
    """Generate a grounded, citation-verified answer from already-
    retrieved, already-judged-relevant chunks. Callers must not invoke
    this with an empty or weak chunk list — see `answer.py`'s "no
    relevant match" short-circuit.

    Returns `None` when the model's answer fails citation verification
    twice in a row (a fabricated chunk_id, or no citation at all, on
    both the original call and the one retry) — the caller
    (`answer.py`) is responsible for falling back to the explicit
    "no relevant match" response in that case.
    """
    if not chunks:
        raise ValueError(
            "generate_answer requires at least one relevant chunk — "
            "callers must short-circuit to the 'no relevant match' "
            "response before calling this function"
        )

    retrieved_ids = {str(c.chunk.id) for c in chunks}

    parsed = _call_model(query, chunks, retry=False)
    if not _verify(parsed, retrieved_ids):
        parsed = _call_model(query, chunks, retry=True)
        if not _verify(parsed, retrieved_ids):
            return None

    cited_ids = {c.chunk_id for c in parsed.citations}
    cited_chunks = [c for c in chunks if str(c.chunk.id) in cited_ids]
    citations = [
        Citation(
            source_document_id=c.source_document.id,
            source_url=c.source_document.source_url,
            verified_at=c.source_document.approved_at,
        )
        for c in cited_chunks
    ]
    return RAGAnswer(
        text=parsed.answer,
        citations=citations,
        cited_chunk_ids=[str(c.chunk.id) for c in cited_chunks],
    )
