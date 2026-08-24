"""6.11.2 contextual question phrasing tests.

The success-path behavior (a rephrasing asking about the right
attribute) is exercised indirectly through the real API in
`tests/api/test_conversation_polish.py`. Here: the two explicit
fallback paths — an attribute mismatch, and a call failure — both of
which must return the canonical prompt unchanged, deterministically
reproduced by mocking the boundary the same way
`tests/rag/test_generation.py` mocks 6.9's verification-gate tests.

Mocked at `app.chat.rephrase.structured_completion` — the
`app.llm.gateway` seam (langgraph-orchestration-branch's LiteLLM
gateway) — rather than at a provider SDK, since which provider serves
this job is now a config value, not a fixed import.
"""

from unittest.mock import patch

from app.chat.rephrase import Rephrasing, rephrase_question

CANONICAL = "How old is the applicant?"


def test_mismatched_attribute_falls_back_to_canonical():
    mismatched = Rephrasing(rephrased_text="Have you changed your name?", target_attribute="name_changed")

    with patch("app.chat.rephrase.structured_completion", return_value=mismatched):
        result = rephrase_question(CANONICAL, "age", ["I'm not sure how old I am"])

    assert result == CANONICAL


def test_api_failure_falls_back_to_canonical():
    with patch("app.chat.rephrase.structured_completion", side_effect=RuntimeError("simulated API failure")):
        result = rephrase_question(CANONICAL, "age", ["My passport expired last year"])

    assert result == CANONICAL


def test_matching_attribute_returns_the_rephrased_text():
    matching = Rephrasing(rephrased_text="How old are you?", target_attribute="age")

    with patch("app.chat.rephrase.structured_completion", return_value=matching):
        result = rephrase_question(CANONICAL, "age", ["My passport expired last year"])

    assert result == "How old are you?"
