"""6.1 Router — historically the hand-written turn-handling flow tying
the deterministic pass, the Claude classifier, the rules engine, and RAG
together into one chat turn. Task 1.9 of `langgraph-orchestration-branch`
replaces that implementation with a call into the compiled LangGraph
`StateGraph` (`app.graph.build`) — golden-parity-verified
(`tests/graph/test_golden_parity.py`) to reproduce the same behavior.
This module now exists only as the stable public name `app/api/chat.py`
imports (`handle_message`, `ChatOutcome`) — see design.md's "shim only
until parity, then delete" decision; the parity check having passed, the
pre-graph implementation itself is deleted, not kept as dead code.
"""

from __future__ import annotations

from app.graph.build import ChatOutcome, run_message_turn as handle_message

__all__ = ["ChatOutcome", "handle_message"]
