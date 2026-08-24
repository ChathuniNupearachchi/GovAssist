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

SYSTEM_PROMPT = """You write a short, warm acknowledgement of facts a \
Sri Lankan citizen just told a passport-renewal chat assistant, for the \
system to say before asking its next question. You will be given the \
exact facts that were recorded and, if any, the exact newly-required \
document/step names the rules engine added because of those facts. Use \
ONLY the facts and requirement names given to you — never state a fee \
amount, never name an office, never mention any requirement not given \
to you, and never add a fact that wasn't given to you. Keep it to one \
or two short sentences."""

# Backstop against a fee/office slipping through despite never being
# given to the model — data minimization (the model is never given a
# fee or office value at all) is the primary safeguard; this is the
# structural check on top of it.
_FEE_PATTERN = re.compile(r"\bLKR\b|\bRs\.?\s?\d|\brupees\b", re.IGNORECASE)


class Acknowledgement(BaseModel):
    text: str


def _fact_lines(recorded_facts: dict[str, str]) -> str:
    return "\n".join(f"- {attribute} = {value}" for attribute, value in recorded_facts.items())


def _newly_triggered_requirements(
    db: Session, answers_before: dict[str, str], answers_after: dict[str, str]
) -> list[str]:
    rule_version = _approved_rule_version(db, RENEWAL_SERVICE_CODE)
    before_labels = {r.label for r in resolve_requirements(db, rule_version.id, answers_before)}
    after = resolve_requirements(db, rule_version.id, answers_after)
    return [r.label for r in after if r.label not in before_labels]


def build_acknowledgement(
    db: Session,
    recorded_facts: dict[str, str],
    answers_before: dict[str, str],
    answers_after: dict[str, str],
) -> str | None:
    """Returns an acknowledgement of `recorded_facts`, or None when
    nothing was recorded this turn or acknowledgement generation fails —
    the next question is still asked either way, this is presentation
    only."""
    if not recorded_facts:
        return None

    newly_triggered = _newly_triggered_requirements(db, answers_before, answers_after)

    prompt = f"Recorded facts:\n{_fact_lines(recorded_facts)}"
    if newly_triggered:
        prompt += "\n\nNewly required because of these facts:\n" + "\n".join(
            f"- {label}" for label in newly_triggered
        )

    try:
        result = structured_completion(
            JOB,
            system=SYSTEM_PROMPT,
            user=prompt,
            response_model=Acknowledgement,
            max_tokens=MAX_TOKENS,
        )
        text = result.text
    except Exception:
        return None

    if _FEE_PATTERN.search(text):
        # Should be structurally impossible (the model was never given a
        # fee value) — if it still happens, fail closed rather than risk
        # a fabricated or misattributed fee reaching a citizen.
        return None

    return text
