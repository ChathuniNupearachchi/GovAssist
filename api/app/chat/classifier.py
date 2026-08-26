"""6.1 Classification, now on Gemini's free tier.

Called only when the deterministic pass (`deterministic.py`) does not
match. Classifies a truncated citizen message into an `intent`
(`situation`/`question`/`answer`), any extractable facts keyed by the
same attribute vocabulary the deterministic pass and the rules engine
use, and whether the message also asks a question — never a fee,
office, or requirement (see the intent-classification spec's
"classifier never produces plan-shaped output" requirement).

Routed through `app.llm.gateway.structured_completion` (langgraph-
orchestration-branch's cost-engineering decision: this is not the
citizen-facing output, so it runs on a free-tier model — Gemini by
default, `LLM_MODEL_CLASSIFY` env var to override; see design.md).
`extracted`'s schema is a fixed set of optional string fields (one per
known attribute) rather than an open `{attribute: value}` map, because
structured-output JSON schemas require `additionalProperties: false` on
every object — an open map keyed by arbitrary attribute names can't be
expressed that way; a fixed field per known attribute can.

Below the confidence threshold, the router must not silently record an
extracted fact against a wrongly-classified message, so this module
enforces that itself: it discards `extracted` and forces
`intent="question"` before returning, per the intent-classification
spec's "low-confidence classification defaults to a question, not a
silent fact" requirement. A failed call (free tier unavailable, rate
limited, malformed response) degrades the same way — any exception from
the gateway is caught and treated identically to a below-threshold
result, per the branch's "a free tier being unavailable must degrade
gracefully, not error" constraint.
"""

from __future__ import annotations

import os
from typing import Literal

from pydantic import BaseModel

from app.llm.gateway import structured_completion

JOB = "classify"

# Unvalidated against real citizen phrasing — see design.md's Risk note.
# A single named constant, matching Phase 5's WEAK_MATCH_THRESHOLD
# precedent, so it's easy to find and retune later.
CONFIDENCE_THRESHOLD = 0.6

SYSTEM_PROMPT = """You classify a Sri Lankan citizen's chat message \
sent while using a passport-renewal intake assistant.

Classify the message into:
- intent: "situation" (states facts about the citizen's case),
  "question" (asks something, states nothing usable as a case fact), or
  "answer" (directly answers the pending intake question, if one is
  given).
- extracted: any of the following facts the message states about the
  citizen's own case, using exactly these value conventions —
  age (a bare number as a string), holds_passport/name_changed/
  dual_citizen/section_19_2/buddhist_priest ("true" or "false"),
  profession (free text), district (a Sri Lankan district name),
  service_basis ("normal" or "urgent"), applying_from ("sri_lanka" or
  "abroad" — infer "abroad" if the citizen names any location outside
  Sri Lanka, e.g. a country or city like "Dubai" or "Australia", or
  says they're overseas/abroad; infer "sri_lanka" if they name a Sri
  Lankan district or say they're in Sri Lanka), lost_passport_age
  ("within_1_year" or "over_1_year" — only for a citizen replacing a
  lost or stolen passport, when they state or imply how long ago it was
  issued), lost_location ("sri_lanka" or "abroad" — only for a citizen
  replacing a lost or stolen passport, where the loss/theft itself
  happened; this can differ from applying_from, e.g. someone who lost
  it abroad but has since returned to Sri Lanka). Leave a field unset
  if the message does not state it. Do not guess or infer a fact the
  message does not actually state.
- contains_question: true if the message asks anything, even if it also
  states facts.
- confidence: your confidence (0 to 1) in this classification overall.

Never invent a fee, an office, or a document requirement — you only
extract facts and detect whether a question was asked; a separate
rules engine computes the plan."""


class ExtractedFacts(BaseModel):
    age: str | None = None
    holds_passport: str | None = None
    name_changed: str | None = None
    dual_citizen: str | None = None
    section_19_2: str | None = None
    profession: str | None = None
    buddhist_priest: str | None = None
    district: str | None = None
    service_basis: str | None = None
    applying_from: str | None = None
    lost_passport_age: str | None = None
    lost_location: str | None = None


class Classification(BaseModel):
    intent: Literal["situation", "question", "answer"]
    extracted: ExtractedFacts
    contains_question: bool
    confidence: float


def _build_prompt(message: str, pending_question: str | None) -> str:
    if pending_question:
        pending_line = f'The pending intake question is: "{pending_question}"'
    else:
        pending_line = "No intake question is currently pending."
    return f'{pending_line}\n\nCitizen message: "{message}"'


_FALLBACK = Classification(
    intent="question", extracted=ExtractedFacts(), contains_question=True, confidence=0.0
)

# Off by default — a citizen's classification is a live API call every
# time, deliberately (a model update should be visible immediately, not
# masked by a stale cache). Enabled only for QA harness runs
# (tests/qa/harness.py sets this env var before driving questions.txt),
# where classify(message, pending_question) is a pure function of its
# two arguments and the SAME scenario text recurs across the 117-line
# question set and across repeated harness runs — re-classifying
# identical (message, pending_question) pairs there is pure wasted
# quota, not a behavior citizens would ever notice. Keyed on both
# arguments, not just the message — the same text means something
# different depending on what's actually pending (a bare "yes" as an
# answer to "are you a dual citizen?" vs. as a reply to nothing).
#
# ALSO keyed on SYSTEM_PROMPT and the resolved model (see _cache_key) —
# a change to either must not be tested against stale cached results.
# A long-lived process's module-level dict would otherwise happily keep
# serving an entry classified under yesterday's prompt/model after
# today's edit; hashing both into the key makes an old entry simply
# unreachable the moment either changes, rather than requiring anyone
# editing this file to remember to also call a separate invalidation
# function. A fresh process (the normal case — every harness/pytest
# invocation starts empty) never needed this; it protects a persistent
# process (a long test session, a notebook) that hot-reloads this
# module mid-session.
_cache: dict[tuple[str, str | None, str], Classification] = {}


def _cache_enabled() -> bool:
    # Checked live, not cached at import time — the QA harness sets this
    # env var right before driving questions.txt, which can be after
    # this module (or `main.app`, which imports it transitively) is
    # already imported.
    return os.environ.get("CLASSIFY_CACHE_ENABLED", "false").strip().lower() == "true"


def _cache_key(message: str, pending_question: str | None) -> tuple[str, str | None, str]:
    from app.llm.gateway import model_for

    prompt_and_model_fingerprint = str(hash((SYSTEM_PROMPT, model_for(JOB))))
    return (message, pending_question, prompt_and_model_fingerprint)


def classify(message: str, pending_question: str | None) -> Classification:
    cache_key = _cache_key(message, pending_question)
    if _cache_enabled() and cache_key in _cache:
        return _cache[cache_key]

    try:
        result = structured_completion(
            JOB,
            system=SYSTEM_PROMPT,
            user=_build_prompt(message, pending_question),
            response_model=Classification,
            max_tokens=512,
        )
    except Exception:
        # Free tier unavailable, rate limited, or an unparseable response
        # — degrade the same way a below-threshold classification already
        # does: no silently-recorded fact, treated as an unanswered
        # question rather than surfacing an error to the citizen. Never
        # cached — a transient failure caching itself would turn one bad
        # moment into a permanent one for the rest of a QA run.
        return _FALLBACK

    if result.confidence < CONFIDENCE_THRESHOLD:
        result = result.model_copy(update={"intent": "question", "extracted": ExtractedFacts()})

    if _cache_enabled():
        _cache[cache_key] = result
    return result
