"""6.11.3 Visible extraction acknowledgement.

Acknowledges exactly the facts a chat turn actually recorded to
CASE_ANSWER, and names any requirement the rules engine newly includes
as a direct result — computed by two real `resolve_requirements` calls
(with and without the new answer(s)), never asserted by the model. The
model is given only already-true, already-computed facts and asked to
phrase them; it has no way to introduce an unrecorded fact or an
uncomputed requirement, and it is never given a fee or office value to
mention in the first place. See design.md's "Acknowledgement:
engine-computed diff, not model-asserted content" decision.

Routed through `app.llm.gateway.structured_completion` to Gemini's free
tier by default (`LLM_MODEL_ACKNOWLEDGE` to override) — langgraph-
orchestration-branch's cost-engineering decision. Not one of the branch
request's explicitly-named jobs (classify/rephrase were named; this
wasn't), but the same profile applies: presentation-only wording around
already-computed facts, running on every turn that records something,
with the structural fee/office backstop below independent of which
model phrases the text. Flagged for confirmation rather than assumed
silently correct.
"""

from __future__ import annotations

import re

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.engine.requirements import resolve_requirements
from app.engine.resolver import RENEWAL_SERVICE_CODE, _approved_rule_version
from app.llm.gateway import structured_completion

JOB = "acknowledge"
MAX_TOKENS = 256

SYSTEM_PROMPT = """You write ONE short line for a passport-service chat \
assistant, spoken right before it asks its next question, reacting to \
what a Sri Lankan citizen just said — the way a helpful person having a \
real conversation would react, not a form clerk confirming a field was \
saved. You will be given the exact facts that were recorded and, if \
any, the exact newly-required document/step the rules engine added \
because of those facts. Use ONLY what you're given — never state a fee \
amount, never name an office, never mention a requirement not given to \
you, and never add a fact you weren't given.

BANNED, under any phrasing: "Thank you", "Thanks for sharing/telling/\
letting", "I have recorded that", "I have noted that", "Let's move on \
to the next step", or any other line that just restates the fact back \
as confirmation of data entry. If you notice yourself about to start \
with "Thank you" or "Thanks", stop and write something else — react to \
what it MEANS, don't just acknowledge that it was received.

TWO CASES:

1. Nothing new was required because of this fact (no second item was \
given to you). React in 2-4 words and move on — vary it naturally \
across a conversation, don't reuse the same word every turn: "Right.", \
"Got it.", "Understood.", "Noted.", "Good,", "Okay —". Do not manufacture \
a reason to be grateful for an answer that changed nothing.

2. Exactly one new requirement was given to you. Say what it actually \
MEANS for the citizen, in plain everyday words — never quote the \
requirement's formal label verbatim (that reads like a document form, \
not a sentence a person would say). Compress it: "Marriage certificate \
with a photocopy where it is necessary (to confirm the name after \
marriage)" becomes something like "you'll need your marriage \
certificate" — drop the legal/procedural qualifiers, keep the plain \
fact. If the fact itself already implies something good or convenient \
(e.g. already holding a passport means one less thing to obtain), you \
can say so.

(A rare third case — two or more new requirements at once — is handled \
before you're even asked; you will simply never be given more than one \
requirement name to work with.)

Keep the whole line under 15 words when possible, never more than one \
short sentence — this is read on a phone, immediately followed by \
another question, so it must be quick to skim, not a second thing to \
read.

Examples (facts -> your line):
- age = 32, new requirement "Provide fingerprints in person at the Head \
Office or a Regional Office" -> "32 — so you'll need to give \
fingerprints in person, which is required for anyone between 16 and 60."
- holds_passport = true, new requirement "Current passport with a \
photocopy of the Bio data page." -> "Good — that saves a step, since \
you'll just submit it with your application."
- name_changed = false, no new requirement -> "Right."
- dual_citizen = false, no new requirement -> "Understood."
- name_changed = true, new requirement "Marriage certificate with a \
photocopy where it is necessary (to confirm the name after marriage)" \
-> "Got it — you'll need your marriage certificate too." """

# Backstop against a fee/office slipping through despite never being
# given to the model — data minimization (the model is never given a
# fee or office value at all) is the primary safeguard; this is the
# structural check on top of it.
_FEE_PATTERN = re.compile(r"\bLKR\b|\bRs\.?\s?\d|\brupees\b", re.IGNORECASE)

# Same data-minimization philosophy, applied to tone: a free-tier model
# asked not to open with "Thank you" still sometimes does (confirmed
# during this fix's own live verification). Rather than trust
# instruction-following alone, a line that slips through with the
# banned opener is discarded — the next question still gets asked, this
# is presentation-only — instead of ever showing the citizen the exact
# form-clerk phrasing this fix exists to remove.
_BANNED_OPENER_PATTERN = re.compile(
    r"^\s*(thank you|thanks for|thanks,|i have (recorded|noted) that|let'?s move on)",
    re.IGNORECASE,
)

# Conversational-quality round: the Groq cross-provider fallback (see
# app.llm.gateway) sometimes trails off with a dash and nothing after
# it — "Okay —" with no second clause — confirmed live during this
# fix's own verification. Cheap, safe cleanup rather than a whole
# retry: strip a trailing em/en-dash or hyphen (with any surrounding
# whitespace) if nothing meaningful follows it.
_DANGLING_DASH_PATTERN = re.compile(r"[\s—–-]+$")
_ENDS_WITH_PUNCTUATION = re.compile(r"[.!?]$")


def _clean_acknowledgement_text(text: str) -> str:
    cleaned = _DANGLING_DASH_PATTERN.sub("", text).rstrip()
    # This line is always immediately followed by the next question (per
    # the "reads as one continuous message" requirement) — a missing
    # full stop reads as a run-on ("Okay What is your job?"), whether or
    # not a dash was stripped. Guaranteed here rather than trusted to
    # the model's own output.
    if cleaned and not _ENDS_WITH_PUNCTUATION.search(cleaned):
        cleaned += "."
    return cleaned


class Acknowledgement(BaseModel):
    text: str


def _fact_lines(recorded_facts: dict[str, str]) -> str:
    return "\n".join(f"- {attribute} = {value}" for attribute, value in recorded_facts.items())


def _newly_triggered_requirements(
    db: Session, service_code: str, answers_before: dict[str, str], answers_after: dict[str, str]
) -> list[str]:
    rule_version = _approved_rule_version(db, service_code)
    before_labels = {r.label for r in resolve_requirements(db, rule_version.id, answers_before)}
    after = resolve_requirements(db, rule_version.id, answers_after)
    return [r.label for r in after if r.label not in before_labels]


def build_acknowledgement(
    db: Session,
    recorded_facts: dict[str, str],
    answers_before: dict[str, str],
    answers_after: dict[str, str],
    service_code: str = RENEWAL_SERVICE_CODE,
) -> str | None:
    """Returns an acknowledgement of `recorded_facts`, or None when
    nothing was recorded this turn or acknowledgement generation fails —
    the next question is still asked either way, this is presentation
    only.

    BUG FIX (conversational-quality round, item 1): `service_code`
    used to be silently hardcoded to renewal's — for any of the other
    six services, the before/after diff was computed against RENEWAL's
    rule version instead of the case's own, so "what's newly required"
    was simply wrong (comparing an unrelated service's conditions,
    producing a coincidental or empty diff) every time this ran for a
    non-renewal case. Defaulted to `RENEWAL_SERVICE_CODE` only so any
    caller that predates this fix keeps working unchanged; the real
    call site (`app.graph.build.run_message_turn`) always passes the
    case's actual `service_code` now."""
    if not recorded_facts:
        return None

    newly_triggered = _newly_triggered_requirements(db, service_code, answers_before, answers_after)

    prompt = f"Recorded facts:\n{_fact_lines(recorded_facts)}"
    if len(newly_triggered) == 1:
        prompt += f"\n\nNewly required because of these facts:\n- {newly_triggered[0]}"
    elif len(newly_triggered) > 1:
        # Structural fix, mirroring the fee backstop's own philosophy:
        # data minimization over trusting instruction-following — a
        # free-tier model asked not to enumerate a list still sometimes
        # does. With 2+ new requirements, the model is never given their
        # names at all, so it is structurally incapable of listing them
        # regardless of how well it follows the "don't enumerate"
        # instruction.
        prompt += (
            f"\n\n{len(newly_triggered)} new requirements were added because of these "
            "facts. Do not ask what they are or name any of them — briefly react that "
            "a bit more is needed now, in the same short, natural style as the examples."
        )

    for _attempt in range(2):
        try:
            result = structured_completion(
                JOB,
                system=SYSTEM_PROMPT,
                user=prompt,
                response_model=Acknowledgement,
                max_tokens=MAX_TOKENS,
            )
            text = _clean_acknowledgement_text(result.text)
        except Exception:
            return None

        if _FEE_PATTERN.search(text):
            # Should be structurally impossible (the model was never
            # given a fee value) — if it still happens, fail closed
            # rather than risk a fabricated or misattributed fee
            # reaching a citizen. Not worth a retry: a leaked fee is a
            # data problem, not a phrasing one a second attempt fixes.
            return None

        if not _BANNED_OPENER_PATTERN.match(text):
            return text
        # One retry, nudged explicitly — a free-tier model asked not to
        # open with "Thank you" still sometimes does; a single retry
        # with a pointed correction is cheap and usually resolves it
        # (confirmed during this fix's own live verification) without
        # falling all the way back to no acknowledgement at all.
        prompt += (
            '\n\n(Your previous attempt opened with a banned phrase like "Thank you" '
            "— try again, reacting to what the fact means, not confirming it was received.)"
        )

    # Both attempts opened with a banned phrase — degrade the same way a
    # generation failure does: no acknowledgement this turn rather than
    # showing the exact form-clerk phrasing this fix exists to remove.
    return None
