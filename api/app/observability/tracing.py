"""Langfuse tracing — Task Group 7.

Self-hosted Langfuse (`docker-compose.yml`'s `langfuse-web`/`langfuse-
worker` services), instrumented via the OTel-based Python SDK's
`start_as_current_observation` context managers. Three call sites use
this module:

- `app.chat.agent` / `app.graph.agent_nodes` wrap each `client.messages.
  create` call with `traced_generation` and each `call_tool` invocation
  with `traced_tool` — the two things a refused turn's trace needs to
  show: which tools the agent called or failed to call, and what each
  model turn actually returned (`stop_reason`, tool choice, or the
  absence of one).
- `app.llm.gateway.structured_completion` wraps the one call site every
  Gemini-routed job (classify/rephrase/acknowledge) shares, so those
  three get "every LLM call" coverage from one instrumentation point
  rather than three.
- `app.graph.nodes` / `app.graph.agent_nodes` wrap every node function
  with `traced_node` — a node isn't a tool call, but the request asks
  for "every graph node transition" traced too.

Every wrapper here is fail-open, per 7.7's explicit requirement — "a
tracing failure must not break the turn": constructing the Langfuse
client, and entering/exiting a span, are wrapped so a Langfuse outage
(the self-hosted stack not running, a network hiccup, a bad response)
can never propagate into the actual chat turn. When Langfuse is
unreachable or unconfigured, every context manager here yields a no-op
span object whose `.update()` does nothing — call sites never need to
branch on whether tracing is actually active.

**Correctness note on what "fail-open" does NOT mean**: only the
Langfuse span's own setup/teardown is caught here — never the wrapped
code's own execution. An exception raised by the code running *inside*
one of these context managers (a real bug in `call_tool`, a node
function, a model call) is allowed to propagate normally, exactly as it
would without tracing. Catching it here would either mask a real defect
as a tracing failure, or (for `traced_node`, which wraps a
side-effecting graph node like `record_facts_node`) risk silently
re-invoking the wrapped function a second time — both worse than the
outage this module exists to be safe against.

Configured via the standard Langfuse env vars (`LANGFUSE_PUBLIC_KEY`,
`LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`) — tracing is off by default
(these have no default value) rather than attempting to reach a
Langfuse instance that was never configured. `LANGFUSE_ENABLED=false`
force-disables it even when keys are present (e.g. running the test
suite without the local Langfuse stack up).
"""

from __future__ import annotations

import functools
import os
import sys
from contextlib import contextmanager
from typing import Any, Callable

try:
    from langfuse import Langfuse, propagate_attributes
except ImportError:  # pragma: no cover - langfuse is a hard dependency once installed
    Langfuse = None
    propagate_attributes = None

_client: "Langfuse | None" = None
_client_attempted = False


class _NoOpSpan:
    """Yielded by every tracing context manager when Langfuse is
    unavailable/unconfigured — call sites call `.update(...)` on
    whatever they get back without needing to check first."""

    def update(self, **_kwargs: Any) -> "_NoOpSpan":
        return self


_NOOP = _NoOpSpan()


class _SafeSpan:
    """Wraps a real Langfuse span so `.update()` itself can never raise
    into caller code — e.g. `state` containing a UUID or datetime that
    the span tries and fails to serialize must not turn a successful
    node/tool call into a broken turn. This is deliberately narrower
    than `_observation`'s own exception handling: that one protects span
    setup/teardown and lets the *wrapped code's* exceptions through
    unchanged; this one protects the *update call itself*, which callers
    invoke from inside their own code after their real work already
    succeeded."""

    def __init__(self, span: Any) -> None:
        self._span = span

    def update(self, **kwargs: Any) -> "_SafeSpan":
        try:
            self._span.update(**kwargs)
        except Exception:
            pass
        return self


def _configured() -> bool:
    if os.environ.get("LANGFUSE_ENABLED", "true").strip().lower() == "false":
        return False
    return bool(os.environ.get("LANGFUSE_PUBLIC_KEY")) and bool(os.environ.get("LANGFUSE_SECRET_KEY"))


def get_client() -> "Langfuse | None":
    """Lazy singleton. Returns None (not raises) when Langfuse isn't
    installed, isn't configured, or fails to construct — every caller
    in this module already treats a None client as "tracing off"."""
    global _client, _client_attempted
    if _client_attempted:
        return _client
    _client_attempted = True
    if Langfuse is None or not _configured():
        return None
    try:
        _client = Langfuse()
    except Exception:
        _client = None
    return _client


@contextmanager
def _observation(name: str, as_type: str, input: Any, model: str | None = None):
    """Shared implementation for every span type below. Only span
    setup/teardown is inside a `try`/`except` — the wrapped code's own
    exceptions always propagate unchanged; see the module docstring's
    correctness note."""
    client = get_client()
    if client is None:
        yield _NOOP
        return

    try:
        kwargs: dict[str, Any] = {"name": name, "as_type": as_type, "input": input}
        if model is not None:
            kwargs["model"] = model
        cm = client.start_as_current_observation(**kwargs)
        span = _SafeSpan(cm.__enter__())
    except Exception:
        yield _NOOP
        return

    try:
        yield span
    except BaseException:
        try:
            cm.__exit__(*sys.exc_info())
        except Exception:
            pass
        raise
    else:
        try:
            cm.__exit__(None, None, None)
        except Exception:
            pass


@contextmanager
def turn_trace(case_id: str | None, query: str):
    """Wraps one full `answer_with_agent` turn as the root span, with
    `case_id` propagated as the Langfuse session_id to every span
    created underneath — this is what makes a case's traces retrievable
    together (7.5)."""
    if propagate_attributes is None:
        with _observation("agent_turn", "agent", query) as span:
            yield span
        return
    with _observation("agent_turn", "agent", query) as span:
        with propagate_attributes(session_id=case_id):
            yield span


@contextmanager
def traced_generation(name: str, model: str, input: Any):
    """One model call (`client.messages.create` or `structured_
    completion`) as a Langfuse generation span."""
    with _observation(name, "generation", input, model=model) as span:
        yield span


@contextmanager
def traced_tool(name: str, input: Any, as_type: str = "tool"):
    """One tool call."""
    with _observation(name, as_type, input) as span:
        yield span


def traced_node(name: str) -> Callable:
    """Decorator for a LangGraph node function `(state, config) -> dict`
    (Task Group 1's graph — `app.graph.nodes`, `app.graph.agent_nodes`).
    Every graph node transition (7.4) gets a span named `node:{name}`,
    input the fields of `state` this node actually reads, output the
    dict it returns; `state["case_id"]`, when present, is propagated as
    the Langfuse session_id to this span and anything nested under it
    (e.g. `agent_node`'s own `traced_generation`/`traced_tool` calls) —
    the graph has no single Python call spanning a whole conversation
    the way `answer_with_agent`'s `turn_trace` does (LangGraph invokes
    each node separately, checkpointed between turns), so session
    propagation happens per-node-call here instead of once at a shared
    root.

    `fn(state, config)` is called exactly once, outside of any
    exception handler that could re-invoke it — see the module
    docstring's correctness note. A tracing failure here degrades to
    calling `fn` untraced, never to calling it twice or swallowing an
    error `fn` itself raised.
    """

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(state: dict, config: Any) -> dict:
            case_id = state.get("case_id")
            node_input = state.get("message") or state.get("action")
            if propagate_attributes is None:
                with _observation(f"node:{name}", "chain", node_input) as span:
                    result = fn(state, config)
                    span.update(output=result)
                    return result
            with _observation(f"node:{name}", "chain", node_input) as span:
                with propagate_attributes(session_id=case_id):
                    result = fn(state, config)
                span.update(output=result)
                return result

        return wrapper

    return decorator


def flush() -> None:
    """Best-effort flush — used by short-lived scripts/tests where the
    process exits before Langfuse's background export would otherwise
    fire. Never raises."""
    client = get_client()
    if client is None:
        return
    try:
        client.flush()
    except Exception:
        pass
