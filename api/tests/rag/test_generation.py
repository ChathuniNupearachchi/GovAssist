"""5.3 Grounded generation unit tests. Calls the real Claude API — no
mocking, consistent with this project's "verify directly" pattern."""

import pytest

from app.rag.generation import generate_answer
from app.rag.retrieval import retrieve


def test_generate_answer_requires_at_least_one_chunk():
    with pytest.raises(ValueError):
        generate_answer([], "irrelevant")


def test_generated_answer_cites_every_passed_chunk(db):
    result = retrieve(db, "What is the fee for a name change amendment?")
    assert result.relevant

    answer = generate_answer(result.chunks, "What is the fee for a name change amendment?")

    assert answer.text
    assert len(answer.citations) == len(result.chunks)
    for citation in answer.citations:
        assert citation.source_url
        assert citation.verified_at is not None
