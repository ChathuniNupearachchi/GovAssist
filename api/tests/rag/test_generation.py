"""5.3 Grounded generation unit tests + 6.9 citation verification tests.

The success-path tests call the real Claude API — no mocking, consistent
with this project's "verify directly" pattern. The verification-gate
tests (fabricated citation, empty citation, retry) mock `_call_model`
directly: reliably provoking the real model into fabricating a citation
on command isn't something a test can depend on, and the task this
phase is built against explicitly calls for "a test that deliberately
injects a fabricated chunk_id into a mocked model response" — the gate
itself is a pure set-membership check, so mocking only the boundary
where the model's structured output enters is enough to exercise it
completely.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.rag.generation import GenerationCitation, StructuredAnswer, generate_answer
from app.rag.retrieval import retrieve


def test_generate_answer_requires_at_least_one_chunk():
    with pytest.raises(ValueError):
        generate_answer([], "irrelevant")


def test_generated_answer_cites_from_the_retrieved_set(db):
    query = "What is the fee for a name change amendment?"
    result = retrieve(db, query)
    assert result.relevant

    answer = generate_answer(result.chunks, query)

    assert answer is not None
    assert answer.text
    assert answer.citations  # a grounded answer always has >=1 citation
    retrieved_urls = {c.source_document.source_url for c in result.chunks}
    for citation in answer.citations:
        assert citation.source_url in retrieved_urls
        assert citation.verified_at is not None


def test_fabricated_citation_is_rejected_and_retried(db):
    query = "What is an authorised photo studio?"
    result = retrieve(db, query)
    retrieved_id = str(result.chunks[0].chunk.id)

    fabricated = StructuredAnswer(
        answer="An answer citing a chunk it was never given.",
        citations=[GenerationCitation(chunk_id="not-a-real-chunk-id", quoted_span="x")],
    )
    corrected = StructuredAnswer(
        answer="A correctly-cited retry.",
        citations=[GenerationCitation(chunk_id=retrieved_id, quoted_span="x")],
    )

    with patch(
        "app.rag.generation._call_model", side_effect=[fabricated, corrected]
    ) as mock_call:
        answer = generate_answer(result.chunks, query)

    assert mock_call.call_count == 2  # the retry path was actually exercised
    assert answer is not None
    assert answer.text == "A correctly-cited retry."
    assert len(answer.citations) == 1


def test_repeated_fabricated_citation_falls_back_to_none(db):
    query = "What is an authorised photo studio?"
    result = retrieve(db, query)

    fabricated = StructuredAnswer(
        answer="Always cites a chunk it was never given.",
        citations=[GenerationCitation(chunk_id="not-a-real-chunk-id", quoted_span="x")],
    )

    with patch(
        "app.rag.generation._call_model", side_effect=[fabricated, fabricated]
    ) as mock_call:
        answer = generate_answer(result.chunks, query)

    assert mock_call.call_count == 2
    assert answer is None


def test_empty_citation_list_is_rejected(db):
    query = "What is an authorised photo studio?"
    result = retrieve(db, query)

    uncited = StructuredAnswer(answer="An answer with no citations at all.", citations=[])

    with patch("app.rag.generation._call_model", side_effect=[uncited, uncited]) as mock_call:
        answer = generate_answer(result.chunks, query)

    assert mock_call.call_count == 2
    assert answer is None
