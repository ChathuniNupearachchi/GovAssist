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

This module still does NOT decide what happens once every option below
is exhausted — a bad response or any other exception is raised straight
through, and each call site already owns (or, for `classify`, owns per
an earlier change) its own fallback: `rephrase_question` falls back to
the canonical prompt, `build_acknowledgement` returns `None`, `classify`
falls back to `intent="question"` with no extracted facts. That keeps
"a free tier being unavailable must degrade gracefully, not error" true
without this module needing to know three different callers' three
different safe defaults. What changed (session that hit Gemini's daily
free-tier quota exhausted mid-QA-run, confirmed directly — a fresh
isolated call still 429'd): this module now tries harder *before*
raising, rather than raising on the first 429:

1. **Key rotation** — `GEMINI_API_KEY` and `GEMINI_API_KEY_2` (a second
   key from a separate Google Cloud project; the free tier is
   per-project, so a second key is genuinely separate quota, not a
   workaround pretending to be one — confirmed directly, the second key
   answered a call after the first was already 429'ing). Only applies
   to `gemini/*` models; every other provider still resolves its
   credential the way LiteLLM/that provider's SDK normally does.
2. **Cross-provider fallback** — once every configured Gemini key is
   rate-limited, `LLM_FALLBACK_MODEL_<JOB>` (Groq's free tier by
   default for `classify`/`rephrase` — generous limits, a different
   company's infrastructure, so a Gemini-wide outage doesn't take both
   down at once) is tried before giving up. Empty/unset for a job means
   no fallback — same as before this change.

Every attempt (each Gemini key, then the fallback) is still one real
provider call — this does not reduce API usage, it only avoids a single
rate-limited key turning into a failed turn when another option was
available. See `app.chat.classifier`'s in-process cache for actual call
reduction during a QA run specifically.

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
from dotenv import load_dotenv
from pydantic import BaseModel

from app.observability.tracing import traced_generation

# Self-sufficient rather than relying on some other imported module
# (app.db.session, app.ingestion.pdf_extraction) having already called
# this — confirmed directly this session: a bare script importing only
# this module's dependency chain never loaded .env, so GROQ_API_KEY
# (needed for the cross-provider fallback below) was silently absent
# from os.environ even though it was genuinely set in the file.
load_dotenv()

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

# Every Gemini key available for rotation, in order — GEMINI_API_KEY
# first, then GEMINI_API_KEY_2 if set. A second key is genuinely
# separate free-tier quota (per-Google-Cloud-project, not per-account),
# confirmed directly this session. Only consulted for gemini/* models —
# see model_for/_is_gemini_model below.
_GEMINI_API_KEYS = [
    key for key in (os.environ.get("GEMINI_API_KEY"), os.environ.get("GEMINI_API_KEY_2")) if key
]

# Cross-provider fallback per job, tried once every Gemini key above is
# rate-limited. Groq's free tier for rephrase/acknowledge by default (a
# different company's infrastructure — a Gemini-wide 429 doesn't take
# this down too); empty for any job not listed means no fallback,
# matching this module's original "raise straight through" behavior.
# `classify` keeps a fallback too, in case Claude itself ever
# rate-limits — harmless safety net, not the primary path.
#
# BUG FIX (conversational-quality round): the model name here
# (`llama-3.3-70b-versatile`) no longer exists on Groq's API at all —
# confirmed directly against `GET /openai/v1/models`, Groq has moved
# off that Llama lineup entirely. This meant the fallback was silently
# broken (every fallback attempt 404'd) for as long as it's been unused
# — invisible until BOTH Gemini keys were rate-limited at once, which
# is exactly what surfaced it here: rephrase/acknowledge degraded to
# their canonical-text/no-acknowledgement fallbacks even though a
# working cross-provider fallback should have caught it first. `gpt-
# oss-120b`, verified directly against this project's own rephrase
# prompt before adopting it. `acknowledge` gets the same fallback now
# too — it never had one before this fix, despite being exactly the
# same free-tier-dependent, citizen-facing-adjacent job as rephrase.
_DEFAULT_FALLBACK_MODEL_BY_JOB = {
    "classify": "groq/openai/gpt-oss-120b",
    "rephrase": "groq/openai/gpt-oss-120b",
    "acknowledge": "groq/openai/gpt-oss-120b",
}

# Per-job default overrides to `DEFAULT_MODEL` — CRITICAL BUG FIX
# (production incident): `classify` sits on the citizen-facing critical
# path (it's the only thing that turns "I am 20 years old" into a
# recorded fact once the deterministic pass doesn't match), so a free
# tier's quota exhaustion there produces a silent quality failure, not
# a harmless degraded fallback the way it does for rephrase/acknowledge
# (a degraded rephrase falls back to canonical text; a degraded
# acknowledgement is just omitted). Moved to Claude Haiku — reliable,
# and fractions of a cent per turn. `rephrase`/`acknowledge` stay on
# `DEFAULT_MODEL` (Gemini) unchanged; still overridable per job via
# `LLM_MODEL_<JOB>`.
_DEFAULT_MODEL_BY_JOB = {
    "classify": "claude-haiku-4-5",
}


def model_for(job: str) -> str:
    """Resolves the model to use for `job` — `LLM_MODEL_<JOB>` (e.g.
    `LLM_MODEL_CLASSIFY`) if set, else this module's per-job default
    (see `_DEFAULT_MODEL_BY_JOB`), else `DEFAULT_MODEL`."""
    return os.environ.get(f"LLM_MODEL_{job.upper()}", _DEFAULT_MODEL_BY_JOB.get(job, DEFAULT_MODEL))


def fallback_model_for(job: str) -> str | None:
    """Resolves the cross-provider fallback for `job` —
    `LLM_FALLBACK_MODEL_<JOB>` if set, else this module's own default
    (Groq for classify/rephrase, none otherwise). Returns None when no
    fallback applies — callers must not attempt one in that case."""
    return os.environ.get(f"LLM_FALLBACK_MODEL_{job.upper()}", _DEFAULT_FALLBACK_MODEL_BY_JOB.get(job))


def _is_gemini_model(model: str) -> bool:
    return model.startswith("gemini/")


def _is_rate_limit_error(exc: Exception) -> bool:
    return "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc) or isinstance(
        exc, getattr(litellm, "RateLimitError", ())
    )


def _complete_once(model: str, messages: list[dict], max_tokens: int, response_model: type[T], api_key: str | None = None):
    kwargs: dict = {"model": model, "max_tokens": max_tokens, "messages": messages, "response_format": response_model}
    if api_key is not None:
        kwargs["api_key"] = api_key
    response = litellm.completion(**kwargs)
    content = response.choices[0].message.content
    return response_model.model_validate_json(content), content


def structured_completion(
    job: str,
    system: str,
    user: str,
    response_model: type[T],
    max_tokens: int = 512,
) -> T:
    """Runs one structured-output completion for `job` and returns a
    validated `response_model` instance.

    Tries, in order, before raising: every rotation key configured for
    a `gemini/*` model (see `_GEMINI_API_KEYS`), then the job's
    cross-provider fallback (see `fallback_model_for`) if one is
    configured — but ONLY on a rate-limit error specifically; any other
    failure (malformed response, a genuine non-quota API error) raises
    immediately, exactly as before, since retrying a different key or
    provider would not fix a bad request or a parsing failure. Once
    every option is exhausted, raises the last exception — still not
    swallowed here; see the module docstring for why each call site
    owns its own fallback instead.

    Wrapped in a Langfuse generation span (Task Group 7) per attempt —
    each key/provider tried is its own real call and its own span, so a
    trace shows exactly which attempt actually succeeded (or that all
    of them failed).
    """
    model = model_for(job)
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    attempts: list[tuple[str, str | None]] = []
    if _is_gemini_model(model) and _GEMINI_API_KEYS:
        attempts.extend((model, key) for key in _GEMINI_API_KEYS)
    else:
        attempts.append((model, None))

    fallback = fallback_model_for(job)
    if fallback:
        attempts.append((fallback, None))

    last_exc: Exception | None = None
    for attempt_model, api_key in attempts:
        with traced_generation(f"gateway:{job}", attempt_model, messages) as gen:
            try:
                result, content = _complete_once(attempt_model, messages, max_tokens, response_model, api_key)
                gen.update(output=content)
                return result
            except Exception as exc:
                gen.update(output={"error": str(exc)})
                last_exc = exc
                if not _is_rate_limit_error(exc):
                    raise
                # Rate-limited on this key/model — try the next one in
                # `attempts`, if any remain.
                continue

    assert last_exc is not None  # attempts is never empty
    raise last_exc
