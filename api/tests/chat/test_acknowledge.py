"""6.11.3 visible extraction acknowledgement tests.

Mocked at `app.chat.acknowledge.structured_completion` — the
`app.llm.gateway` seam (langgraph-orchestration-branch's LiteLLM
gateway) — rather than at a provider SDK, since which provider serves
this job is now a config value, not a fixed import.
"""

from unittest.mock import patch

import pytest

from app.chat.acknowledge import Acknowledgement, _clean_acknowledgement_text, build_acknowledgement


def test_no_recorded_facts_produces_no_acknowledgement(db):
    result = build_acknowledgement(db, {}, {}, {})
    assert result is None


@pytest.mark.real_api
def test_name_change_acknowledges_the_marriage_certificate_requirement(db):
    """DONE WHEN: "I got married and my name is different now" -> the
    engine's own before/after diff includes the marriage certificate
    requirement, and the acknowledgement names it. The renewal service's
    marriage-certificate requirement is gated on both `name_changed ==
    true` AND `dual_citizen != true` (see app/engine/conditions.py's
    "a missing answer is always not-satisfied" rule) — dual_citizen must
    already be answered for the diff to trigger, matching the real
    intake order (dual_citizen is asked before name_changed's downstream
    effects would otherwise be visible)."""
    result = build_acknowledgement(
        db,
        recorded_facts={"name_changed": "true"},
        answers_before={"age": "34", "dual_citizen": "false"},
        answers_after={"age": "34", "dual_citizen": "false", "name_changed": "true"},
    )
    assert result is not None
    assert "marriage" in result.lower() or "certificate" in result.lower()


def test_acknowledgement_generation_failure_returns_none(db):
    with patch(
        "app.chat.acknowledge.structured_completion",
        side_effect=RuntimeError("simulated API failure"),
    ):
        result = build_acknowledgement(
            db,
            recorded_facts={"age": "34"},
            answers_before={},
            answers_after={"age": "34"},
        )

    assert result is None


def test_acknowledgement_never_states_a_fee_even_if_the_model_tries(db):
    """Structural guard, not just prompt instruction: even if a mocked
    model response smuggles a fee-shaped string past the prompt, the
    regex backstop discards it rather than passing it through."""
    fee_leaking = Acknowledgement(text="Noted — that'll be LKR 10,000. How old are you?")

    with patch("app.chat.acknowledge.structured_completion", return_value=fee_leaking):
        result = build_acknowledgement(
            db,
            recorded_facts={"age": "34"},
            answers_before={},
            answers_after={"age": "34"},
        )

    assert result is None


def test_dangling_dash_is_stripped_and_a_full_stop_added():
    """Conversational-quality round: the Groq cross-provider fallback
    sometimes trails off with a dash and nothing after it ("Okay —"),
    confirmed live — the acknowledgement is always immediately followed
    by the next question, so a missing terminal punctuation reads as a
    run-on once joined."""
    assert _clean_acknowledgement_text("Okay —") == "Okay."
    assert _clean_acknowledgement_text("Right - ") == "Right."


def test_a_normal_acknowledgement_is_unchanged():
    assert _clean_acknowledgement_text("Got it — you'll need your marriage certificate.") == (
        "Got it — you'll need your marriage certificate."
    )
    assert _clean_acknowledgement_text("Right.") == "Right."
