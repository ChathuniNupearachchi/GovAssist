"""Import this before anything else that imports `ragas`.

`ragas==0.4.3`'s `ragas/llms/base.py` unconditionally does `from
langchain_community.chat_models.vertexai import ChatVertexAI` at import
time — a real upstream compatibility bug, not a version this project
chose: the currently-installed `langchain-community==0.4.2` (itself
required by `langgraph`'s dependency chain — an older langchain-core
compatible with ragas's own langchain-community pin breaks `langgraph`
outright, confirmed directly) has dropped that submodule entirely as
part of its "sunset" deprecation, moving VertexAI support to a separate
package this project has no other reason to install. This project never
uses VertexAI (Claude only, per CLAUDE.md), so a stub module satisfying
the import — never instantiated, never called — is the minimal fix.
Confirmed directly: downgrading langchain-community to restore the real
module breaks `langgraph` (needs `langchain-core>=1.4.7`; the
langchain-community version with `chat_models.vertexai` intact pulls in
`langchain-core<1.0`), so that path was rejected, not overlooked.
"""

from __future__ import annotations

import sys
import types

if "langchain_community.chat_models.vertexai" not in sys.modules:
    _stub = types.ModuleType("langchain_community.chat_models.vertexai")

    class ChatVertexAI:  # pragma: no cover - never instantiated, satisfies the import only
        pass

    _stub.ChatVertexAI = ChatVertexAI
    sys.modules["langchain_community.chat_models.vertexai"] = _stub
