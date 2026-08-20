"""6.1 Claude-based classification.

Called only when the deterministic pass (`deterministic.py`) does not
match. Classifies a truncated citizen message into an `intent`
(`situation`/`question`/`answer`), any extractable facts keyed by the
same attribute vocabulary the deterministic pass and the rules engine
use, and whether the message also asks a question — never a fee,
office, or requirement (see the intent-classification spec's
"classifier never produces plan-shaped output" requirement).

Uses `claude-haiku-4-5` via `client.messages.parse()` with a Pydantic
`output_format` — the SDK's structured-outputs path, equivalent to a
raw `output_config.format` json_schema call. `extracted`'s schema is a
fixed set of optional string fields (one per known attribute) rather
than an open `{attribute: value}` map, because structured-output JSON
schemas require `additionalProperties: false` on every object — an
open map keyed by arbitrary attribute names can't be expressed that
way; a fixed field per known attribute can.

Below the confidence threshold, the router must not silently record an
extracted fact against a wrongly-classified message, so this module
enforces that itself: it discards `extracted` and forces
`intent="question"` before returning, per the intent-classification
spec's "low-confidence classification defaults to a question, not a
silent fact" requirement.
"""

from __future__ import annotations

from typing import Literal

import anthropic
from pydantic import BaseModel

MODEL = "claude-haiku-4-5"

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
  service_basis ("normal" or "urgent"). Leave a field unset if the
  message does not state it. Do not guess or infer a fact the message
  does not actually state.
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


def classify(message: str, pending_question: str | None) -> Classification:
    client = anthropic.Anthropic()
    response = client.messages.parse(
        model=MODEL,
        max_tokens=512,
        system=SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": _build_prompt(message, pending_question)}
        ],
        output_format=Classification,
    )
    result = response.parsed_output

    if result.confidence < CONFIDENCE_THRESHOLD:
        return result.model_copy(
            update={"intent": "question", "extracted": ExtractedFacts()}
        )
    return result
