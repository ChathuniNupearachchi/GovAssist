"""Top-level entry point tying retrieval, self-check, and generation
together, and the "I don't have that information" response RAG returns
when retrieval finds no relevant match.

RAG never produces a plan, fee, office, or checklist — CaseAnswer here
is structurally incapable of carrying any of those (contrast with
`app.engine.types.CaseResolution`, the rules engine's return type).
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.engine.types import Citation
from app.rag.generation import RAGAnswer, generate_answer
from app.rag.retrieval import retrieve

NO_MATCH_TEXT = "I don't have that information."


@dataclass(frozen=True)
class RAGResponse:
    text: str
    citations: list[Citation]
    grounded: bool  # False only for the "no relevant match" response


def answer_question(db: Session, query: str) -> RAGResponse:
    result = retrieve(db, query)
    if not result.relevant:
        return RAGResponse(text=NO_MATCH_TEXT, citations=[], grounded=False)

    answer: RAGAnswer = generate_answer(result.chunks, query)
    return RAGResponse(text=answer.text, citations=answer.citations, grounded=True)
