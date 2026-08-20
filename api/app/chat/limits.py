"""6.2 Input limits.

Every citizen message is truncated before it reaches any model call —
the deterministic pass, the Claude classifier, or RAG generation. This
is the single entry point every route funnels through: `chat.router.
handle_message` calls this first, so no route re-implements its own
cap (see the intent-classification spec's "Every message is truncated
before any model call" requirement).
"""

from __future__ import annotations

MAX_MESSAGE_CHARACTERS = 2_000


def truncate_message(text: str) -> str:
    """Truncate to the first MAX_MESSAGE_CHARACTERS characters."""
    return text[:MAX_MESSAGE_CHARACTERS]
