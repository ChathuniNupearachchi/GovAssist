"""Task 1.6 — the LangGraph Postgres checkpointer.

Owns its own tables (`langgraph-checkpoint-postgres`'s own `.setup()`
migration), entirely separate from `app.models.Base` / Alembic — see
design.md's "Postgres checkpointer, not a new bespoke table" decision.
It persists the graph's execution position (`GraphState`) for a
conversation thread; `CASE_ANSWER` remains the sole store of facts the
rules engine evaluates, per the graph-orchestration spec.

Uses the same `DATABASE_URL` as the rest of the app (a plain
`postgresql://` URL, which `psycopg` v3 accepts directly — no
`+psycopg`/`+psycopg2` driver suffix needed).
"""

from __future__ import annotations

import psycopg
from langgraph.checkpoint.postgres import PostgresSaver

from app.db.session import DATABASE_URL

_checkpointer: PostgresSaver | None = None
_conn: psycopg.Connection | None = None


def get_checkpointer() -> PostgresSaver:
    """Returns a process-wide `PostgresSaver`, created and `.setup()` the
    first time it's needed. `autocommit=True` matches the checkpointer's
    own expectation (it manages its own transactions per write)."""
    global _checkpointer, _conn
    if _checkpointer is None:
        _conn = psycopg.connect(DATABASE_URL, autocommit=True)
        _checkpointer = PostgresSaver(_conn)
        _checkpointer.setup()
    return _checkpointer


def reset_checkpointer_for_tests() -> None:
    """Test-only: drops the cached singleton so a fresh connection/setup
    runs on next use — needed when tests tear down and recreate the
    database between runs."""
    global _checkpointer, _conn
    if _conn is not None:
        _conn.close()
    _checkpointer = None
    _conn = None
