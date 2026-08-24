"""Shared fakes for the graph's agent-cycle tests — same mocking seams
`tests/chat/test_router.py` uses (`app.graph.agent_nodes.anthropic.
Anthropic`), factored out so 1.11-1.14's tests don't each redefine them.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.graph import agent_nodes


def text_response(text: str = "Some plain-text response."):
    return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=text)])


def tool_use_response(*calls: tuple[str, dict, str]):
    """`calls` is a sequence of (tool_name, tool_input, tool_id)."""
    return SimpleNamespace(
        stop_reason="tool_use",
        content=[
            SimpleNamespace(type="tool_use", id=tool_id, name=name, input=tool_input)
            for name, tool_input, tool_id in calls
        ],
    )


def submit_answer_response(answer_input: dict, tool_id: str = "toolu_submit"):
    return tool_use_response(("submit_answer", answer_input, tool_id))


class _FakeMessages:
    def __init__(self, responses):
        self._responses = list(responses)

    def create(self, **kwargs):
        if len(self._responses) > 1:
            return self._responses.pop(0)
        return self._responses[0]


class _FakeAnthropicClient:
    def __init__(self, responses):
        self.messages = _FakeMessages(responses)


@pytest.fixture()
def mock_agent_client(monkeypatch):
    def _apply(*responses):
        # `agent_node` calls `anthropic.Anthropic()` fresh on every node
        # invocation (once per turn through the agent<->tools cycle) —
        # the fake client (and its response-consumption state) must be
        # built ONCE per test and reused across every call, not
        # recreated per call, or it never advances past the first
        # response and the cycle spins until MAX_TOOL_ITERATIONS trips.
        shared_client = _FakeAnthropicClient(responses)
        monkeypatch.setattr(agent_nodes.anthropic, "Anthropic", lambda: shared_client)

    return _apply
