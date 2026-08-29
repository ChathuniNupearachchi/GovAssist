"""6.11.1 agent loop tests.

The multi-step chaining test calls the real Claude API — no mocking,
same "verify directly" approach the rest of this project's RAG/
classifier tests use. The failure-path tests (API error, malformed tool
call, fabricated value) mock only the boundary needed to deterministically
reproduce that specific failure, matching `tests/rag/test_generation.py`'s
precedent for 6.9's verification-gate tests.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.chat.agent import _verify_submission, answer_with_agent
from app.db.session import SessionLocal
from app.engine.resolver import RENEWAL_SERVICE_CODE
from app.models import Case, CaseAnswer, Service


def _make_case(device_ref: str) -> Case:
    db = SessionLocal()
    try:
        service = db.query(Service).filter(Service.code == RENEWAL_SERVICE_CODE).first()
        case = Case(service_id=service.id, device_ref=device_ref)
        db.add(case)
        db.commit()
        db.refresh(case)
        return case
    finally:
        db.close()


def _delete_case(case_id) -> None:
    db = SessionLocal()
    try:
        db.query(CaseAnswer).filter(CaseAnswer.case_id == case_id).delete()
        db.query(Case).filter(Case.id == case_id).delete()
        db.commit()
    finally:
        db.close()


@pytest.mark.real_api
def test_amend_vs_renew_produces_a_multi_step_trace_with_both_fees(db):
    """DONE WHEN: "Should I amend my passport or get a new one?" calls
    get_fee twice and retrieve_documents at least once, and states both
    fees with citations."""
    result = answer_with_agent(db, "Should I amend my passport or get a new one?")
    assert result is not None

    tool_names = [record.tool for record in result.trace]
    assert tool_names.count("get_fee") >= 2
    assert tool_names.count("retrieve_documents") >= 1

    fee_amounts = {
        record.result["fee"]["base_amount"]
        for record in result.trace
        if record.tool == "get_fee" and record.result.get("found")
    }
    assert 10000.0 in fee_amounts  # renewal, normal
    assert 1200.0 in fee_amounts  # amendment, normal

    assert "10,000" in result.text or "10000" in result.text
    assert "1,200" in result.text or "1200" in result.text
    assert result.citations


def test_verify_submission_rejects_a_fee_no_tool_returned():
    error = _verify_submission(
        {
            "chunk_citations": [],
            "fee_values_used": [99999.0],
            "office_names_used": [],
            "requirement_labels_used": [],
        },
        chunk_lookup={},
        fee_values=set(),
        office_names=set(),
        requirement_labels=set(),
    )
    assert error is not None
    assert "99999" in error


def test_verify_submission_rejects_an_office_no_tool_returned():
    error = _verify_submission(
        {
            "chunk_citations": [],
            "fee_values_used": [],
            "office_names_used": ["Made Up Office"],
            "requirement_labels_used": [],
        },
        chunk_lookup={},
        fee_values=set(),
        office_names={"Head Office"},
        requirement_labels=set(),
    )
    assert error is not None


def test_verify_submission_rejects_a_chunk_citation_not_retrieved():
    error = _verify_submission(
        {
            "chunk_citations": [{"chunk_id": "not-a-real-chunk", "quoted_span": "x"}],
            "fee_values_used": [],
            "office_names_used": [],
            "requirement_labels_used": [],
        },
        chunk_lookup={"real-chunk-id": {}},
        fee_values=set(),
        office_names=set(),
        requirement_labels=set(),
    )
    assert error is not None


def test_verify_submission_accepts_only_tool_returned_values():
    error = _verify_submission(
        {
            "chunk_citations": [{"chunk_id": "real-chunk-id", "quoted_span": "x"}],
            "fee_values_used": [10000.0],
            "office_names_used": ["Head Office"],
            "requirement_labels_used": ["Photo studio acknowledgement"],
        },
        chunk_lookup={"real-chunk-id": {}},
        fee_values={10000.0},
        office_names={"Head Office"},
        requirement_labels={"Photo studio acknowledgement"},
    )
    assert error is None


def test_api_failure_during_tool_selection_falls_back_to_none(db):
    with patch("app.chat.agent.anthropic.Anthropic") as mock_anthropic_cls:
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = RuntimeError("simulated API failure")
        mock_anthropic_cls.return_value = mock_client

        result = answer_with_agent(db, "What is an authorised photo studio?")

    assert result is None


def test_malformed_tool_call_from_the_model_does_not_crash(db):
    """A mocked model response requests get_fee with an argument
    get_fee doesn't accept — the loop must recover, not raise."""

    def _tool_use_block(name, input_):
        block = MagicMock()
        block.type = "tool_use"
        block.name = name
        block.input = input_
        block.id = f"toolu_{name}"
        return block

    malformed_response = MagicMock()
    malformed_response.stop_reason = "tool_use"
    malformed_response.content = [_tool_use_block("get_fee", {"wrong_field": "oops"})]

    give_up_response = MagicMock()
    give_up_response.stop_reason = "end_turn"
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = "I don't have enough information."
    give_up_response.content = [text_block]

    with patch("app.chat.agent.anthropic.Anthropic") as mock_anthropic_cls:
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [malformed_response, give_up_response]
        mock_anthropic_cls.return_value = mock_client

        result = answer_with_agent(db, "What is the fee?")

    # No exception raised — the malformed call was handled as a tool
    # error and the loop completed (here, by giving up cleanly).
    assert result is None
