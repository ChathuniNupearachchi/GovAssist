"""6.2 Top-level answer entry point unit tests."""

from app.rag.answer import NO_MATCH_TEXT, RAGResponse, answer_question


def test_answer_question_never_carries_plan_fee_office_fields():
    # RAGResponse structurally cannot carry a requirement set, fee, or
    # office field — this is a type-level check, not just a runtime one.
    field_names = set(RAGResponse.__dataclass_fields__.keys())
    assert field_names == {"text", "citations", "grounded"}
    assert "requirements" not in field_names
    assert "fee" not in field_names
    assert "offices" not in field_names


def test_no_relevant_match_returns_explicit_response_no_generation_call(db):
    response = answer_question(db, "What is the weather forecast for Paris tomorrow?")
    assert response.grounded is False
    assert response.text == NO_MATCH_TEXT
    assert response.citations == []


def test_grounded_answer_returns_citations(db):
    response = answer_question(db, "What is an authorised photo studio?")
    assert response.grounded is True
    assert response.text
    assert response.citations
    for citation in response.citations:
        assert citation.source_url
        assert citation.verified_at is not None
