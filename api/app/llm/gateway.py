"""Provider-agnostic structured-output gateway, built on LiteLLM.

Cost-engineering decision (langgraph-orchestration-branch, "free tiers
wherever the output is not citizen-facing"): this project has a fixed
student-project budget, and only one job — `app.chat.agent`'s tool-using,
citizen-facing answer composer — is the output anyone actually judges the
system on. Every other narrow Claude job this project defined (intent
classification, question rephrasing, fact acknowledgement) is presentation
or extraction work that runs on every turn regardless of what the citizen
sees next, so it is moved to a free-tier model instead. See design.md's
"LiteLLM gateway" decision for the full reasoning and the measured
before/after cost per conversation.

This module is the single seam: every call site names a `job` (one of
`classify`, `rephrase`, `acknowledge` today) and gets back a validated
Pydantic instance. Which literal model serves that job is an environment
variable, `LLM_MODEL_<JOB>` (e.g. `LLM_MODEL_CLASSIFY`), defaulting to
Gemini's free tier — so swapping a job back to Claude (or to any of
LiteLLM's 100+ other supported providers) if a free tier proves
inadequate is a config change, not a code change, per the branch's
explicit goal of making every provider swap reversible.

This module does NOT decide what happens on failure — a bad response, a
rate-limited free tier, or any other exception is raised straight through.
Each call site already owns (or, for `classify`, now owns per this
change) its own fallback: `rephrase_question` falls back to the canonical
prompt, `build_acknowledgement` returns `None`, `classify` falls back to
`intent="question"` with no extracted facts — the same "low-confidence
defaults to a question" shape the intent-classification spec already
requires for a low-*confidence* result, now covering a failed call too.
That keeps "a free tier being unavailable must degrade gracefully, not
error" true without this module needing to know three different callers'
three different safe defaults.

`app.chat.agent` (the one job kept on Claude) is intentionally NOT routed
through this gateway — it calls the `anthropic` SDK directly, unchanged,
because it uses Anthropic-native tool-calling (tool_choice, tool_result
blocks) that has no equivalent structured-output shape here, and because
routing the one component this project's quality is judged on through an
extra abstraction layer buys reversibility it doesn't need (nothing else
in this project ever calls the agent's job with a different provider).
"""

from __future__ import annotations

import os
from typing import TypeVar

import litellm
from pydantic import BaseModel

from app.observability.tracing import traced_generation

T = TypeVar("T", bound=BaseModel)

# Gemini's free tier, per the branch's cost-engineering decision. Any
# LiteLLM-supported model string works here — e.g. "claude-haiku-4-5" to
# route a job back to Claude, or another provider's free tier — without
# touching gateway.py or any call site.
# gemini-flash-lite-latest, not the full gemini-3.6-flash: confirmed
# directly (tests/eval/ragas_baseline.py hit a live 429) that the full
# flash model's free tier caps out at 5 requests/minute AND 20/day per
# project per model — far too little for jobs that run on every chat
# turn. The lite model has materially more free-tier headroom.
DEFAULT_MODEL = os.environ.get("LLM_MODEL_DEFAULT", "gemini/gemini-flash-lite-latest")


def model_for(job: str) -> str:
    """Resolves the model to use for `job` — `LLM_MODEL_<JOB>` (e.g.
    `LLM_MODEL_CLASSIFY`) if set, else `DEFAULT_MODEL`."""
    return os.environ.get(f"LLM_MODEL_{job.upper()}", DEFAULT_MODEL)


def structured_completion(
    job: str,
    system: str,
    user: str,
    response_model: type[T],
    max_tokens: int = 512,
) -> T:
    """Runs one structured-output completion for `job` and returns a
    validated `response_model` instance.

    Raises on any failure (API error, rate limit, malformed/unparseable
    response) — deliberately not swallowed here; see the module
    docstring for why each call site owns its own fallback instead.
    Wrapped in a Langfuse generation span (Task Group 7) — this one call
    site covers "every LLM call" for all three Gemini-routed jobs
    (classify/rephrase/acknowledge) at once, rather than instrumenting
    each of their three modules separately.
    """
    model = model_for(job)
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    with traced_generation(f"gateway:{job}", model, messages) as gen:
        response = litellm.completion(
            model=model,
            max_tokens=max_tokens,
            messages=messages,
            response_format=response_model,
        )
        content = response.choices[0].message.content
        result = response_model.model_validate_json(content)
        gen.update(output=content)
        return result
