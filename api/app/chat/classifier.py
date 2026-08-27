"""6.1 Classification.

Called only when the deterministic pass (`deterministic.py`) does not
match. Classifies a truncated citizen message into an `intent`
(`situation`/`question`/`answer`), any extractable facts keyed by the
same attribute vocabulary the deterministic pass and the rules engine
use, and whether the message also asks a question — never a fee,
office, or requirement (see the intent-classification spec's
"classifier never produces plan-shaped output" requirement).

CRITICAL BUG FIX (production incident — see this change's own report):
two things were wrong here, both now fixed.

1. **Schema shape broke on Claude.** `ExtractedFacts` used to be 19
   separate `str | None` fields — a Pydantic model with that many
   nullable fields compiles to a JSON schema with 19 `anyOf`/nullable
   parameters, which Anthropic's structured-output path rejects
   outright ("Schema is too complex" — confirmed directly against the
   live API before this fix). Gemini tolerated the wide schema, which is
   exactly why this went unnoticed while classification lived there.
   Replaced with `extracted: list[ExtractedFact]`, each a small
   `{attribute, value}` pair — the model only ever needs to state the
   handful of facts an actual message contains, not leave 18 fields
   null, and the schema this compiles to is small regardless of how
   many attributes exist project-wide.
2. **A degraded classification was indistinguishable from a genuine
   "this is a question."** Below the confidence threshold, or on any
   exception (free tier unavailable, rate limited, malformed response),
   this module used to force `intent="question"` — nothing distinguished
   "the model genuinely detected a question" from "classification
   failed and we're guessing." Downstream, both routed identically to
   the full tool-agent, which had nothing to answer and produced "I
   don't have that information" while a citizen was mid-sentence
   answering a pending question. Replaced with an explicit `unclear`
   flag: a degraded result now sets `unclear=True` and leaves `intent`
   as `"question"` only as legacy metadata — `app.graph.nodes.
   classify_node` checks `unclear` first, and when a question is
   pending, never routes an unclear result to the agent; it re-asks
   plainly instead. See that module for the routing logic.

Routed through `app.llm.gateway.structured_completion`. `classify`
itself now defaults to Claude Haiku (`app.llm.gateway`'s per-job
default), not Gemini's free tier — this is the one job on the
citizen-facing critical path where free-tier quota exhaustion produces
a silent quality failure, not a harmless degraded fallback (unlike
rephrase/acknowledge, which stay on Gemini: a degraded rephrase falls
back to canonical question text harmlessly, a degraded acknowledgement
just omits one). `LLM_MODEL_CLASSIFY` still overrides if needed.
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

# Every attribute the deterministic pass and the rules engine know
# about — kept as a plain list (not imported from renewal_intake) so
# this module has no import-time dependency on the engine layer; the
# two are cross-checked by tests/chat/test_classifier.py instead.
KNOWN_ATTRIBUTES = [
    "age", "holds_passport", "name_changed", "dual_citizen", "section_19_2",
    "profession", "buddhist_priest", "district", "photo_district", "service_basis",
    "applying_from", "lost_passport_age", "lost_location", "alteration_type",
    "validity_period", "parents_hold_passport", "child_previously_in_parent_passport",
    "parent_circumstance", "child_adopted", "child_born_overseas",
]

SYSTEM_PROMPT = """You classify a Sri Lankan citizen's chat message \
sent while using a passport-service intake assistant.

Classify the message into:
- intent: "situation" (states facts about the citizen's case),
  "question" (asks something, states nothing usable as a case fact), or
  "answer" (directly answers the pending intake question, if one is
  given). A message with extra words around a direct answer — "I am 20
  years old", "yes I still have it", "I'm from Colombo district" — is
  still "answer": most real citizens answer in a full sentence, not a
  bare word, and that must not be misread as a question.
- extracted: a list of {attribute, value} pairs for every fact the
  message actually states about the citizen's own case. Valid
  attributes and their value conventions —
  age (a bare number as a string), holds_passport/name_changed/
  dual_citizen/section_19_2/buddhist_priest ("true" or "false"),
  profession (free text), district (a Sri Lankan district name — where
  the citizen is applying from), photo_district (a Sri Lankan district
  name — only when a separate question about where the citizen will
  take their passport PHOTOGRAPH is pending; this can differ from
  district, e.g. applying in Colombo but photographing in Gampaha),
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
  it abroad but has since returned to Sri Lanka), alteration_type
  ("change_of_name", "profession_inclusion", "nic_inclusion",
  "cancel_single_journey", "cancel_india_nepal", or "other" — only for
  a citizen amending an existing passport, which alteration they want),
  validity_period ("3_year" or "10_year" — only for a child's passport,
  which validity tier), parents_hold_passport ("true"/"false" — only
  for a child's passport, whether both parents currently hold a valid
  Sri Lankan passport), child_previously_in_parent_passport
  ("true"/"false" — only for a child's passport, whether the child was
  ever included in a parent's passport before), parent_circumstance
  ("none", "deceased", "divorced", or "abandoned" — only for a child's
  passport, the family circumstance that applies, if any),
  child_adopted ("true"/"false" — only for a child's passport, whether
  the child is adopted), child_born_overseas ("true"/"false" — only for
  a child's passport, whether the child was born outside Sri Lanka).
  Omit an attribute entirely if the message does not state it. Do not
  guess or infer a fact the message does not actually state. If a
  pending question is given, prioritize extracting that attribute.
- contains_question: true if the message asks anything, even if it also
  states facts.
- confidence: your confidence (0 to 1) in this classification overall.

Never invent a fee, an office, or a document requirement — you only
extract facts and detect whether a question was asked; a separate
rules engine computes the plan."""


class ExtractedFact(BaseModel):
    attribute: Literal[
        "age", "holds_passport", "name_changed", "dual_citizen", "section_19_2",
        "profession", "buddhist_priest", "district", "photo_district", "service_basis",
        "applying_from", "lost_passport_age", "lost_location", "alteration_type",
        "validity_period", "parents_hold_passport", "child_previously_in_parent_passport",
        "parent_circumstance", "child_adopted", "child_born_overseas",
    ]
    value: str


class Classification(BaseModel):
    intent: Literal["situation", "question", "answer"]
    extracted: list[ExtractedFact] = []
    contains_question: bool
    confidence: float
    # True when this result is a degraded fallback (an exception, or a
    # below-threshold confidence) rather than a genuine classification.
    # `intent` stays "question" on an unclear result purely as legacy
    # metadata for any caller that doesn't check this flag; every call
    # site that matters (classify_node) checks `unclear` first. See this
    # module's docstring, fix #2.
    unclear: bool = False

    def extracted_dict(self) -> dict[str, str]:
        return {fact.attribute: fact.value for fact in self.extracted}


def _build_prompt(message: str, pending_question: str | None) -> str:
    if pending_question:
        pending_line = f'The pending intake question is: "{pending_question}"'
    else:
        pending_line = "No intake question is currently pending."
    return f'{pending_line}\n\nCitizen message: "{message}"'


_FALLBACK = Classification(intent="question", extracted=[], contains_question=False, confidence=0.0, unclear=True)

# Off by default — a citizen's classification is a live API call every
# time, deliberately (a model update should be visible immediately, not
# masked by a stale cache). Enabled only for QA harness runs
# (tests/qa/harness.py sets this env var before driving questions.txt),
# where classify(message, pending_question) is a pure function of its
# two arguments and the SAME scenario text recurs across the question
# set and across repeated harness runs — re-classifying identical
# (message, pending_question) pairs there is pure wasted quota, not a
# behavior citizens would ever notice. Keyed on both arguments, not just
# the message — the same text means something different depending on
# what's actually pending (a bare "yes" as an answer to "are you a dual
# citizen?" vs. as a reply to nothing).
#
# ALSO keyed on SYSTEM_PROMPT and the resolved model (see _cache_key) —
# a change to either must not be tested against stale cached results.
_cache: dict[tuple[str, str | None, str], Classification] = {}


def _cache_enabled() -> bool:
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
        # Free tier/provider unavailable, rate limited, or an
        # unparseable response — degrade explicitly via `unclear=True`
        # rather than forcing `intent="question"` as the only signal
        # (fix #2 above). Never cached — a transient failure caching
        # itself would turn one bad moment into a permanent one.
        return _FALLBACK

    if result.confidence < CONFIDENCE_THRESHOLD:
        result = result.model_copy(update={"intent": "question", "extracted": [], "unclear": True})

    if _cache_enabled():
        _cache[cache_key] = result
    return result
