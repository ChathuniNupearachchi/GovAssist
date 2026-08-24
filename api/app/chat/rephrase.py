"""6.11.2 Contextual question phrasing.

Rewrites only the surface wording of the next pending question — WHICH
question gets asked stays `app.engine.next_question`'s untouched,
deterministic decision; this module runs strictly after that decision
has already been made, and can only affect the sentence shown, never
which attribute it's about.

Same structured-output shape as `app.chat.classifier`
(`app.llm.gateway.structured_completion` + a Pydantic response model),
routed to Gemini's free tier by default (`LLM_MODEL_REPHRASE` to
override) — langgraph-orchestration-branch's cost-engineering decision:
this is presentation-only wording, not the citizen-facing agent output,
and it runs on every turn. Two independent fallbacks to the canonical
prompt: the model's own reported `target_attribute` not matching the
actual pending attribute, and any call failure at all (API error,
timeout, rate-limited free tier, malformed response). Either way, the
canonical prompt — never the rephrased text — is what `app.chat.router`
persists as the case's pending-question reference and what test/log
code compares an incoming answer against; see design.md's "Contextual
rephrasing" decision.
"""

from __future__ import annotations

from pydantic import BaseModel

from app.chat.limits import truncate_message
from app.llm.gateway import structured_completion

JOB = "rephrase"
MAX_TOKENS = 256

SYSTEM_PROMPT = """You rewrite one intake question's surface wording for \
a Sri Lankan citizen using a passport-renewal chat assistant, given the \
canonical question, the attribute it asks about, and the last couple of \
turns of conversation (including the citizen's most recent message).

ALWAYS rewrite it into short, warm, first/second-person conversational \
phrasing — never return the canonical wording unchanged. The canonical \
prompts are written in bureaucratic third person ("How old is the \
applicant?", "Do you still hold your current or a previous passport?") \
precisely because they're the system's internal record, not what a \
citizen should read; your job is to convert that into how a helpful \
person would actually ask it out loud, every single time, not only when \
the conversation gives you an obvious hook.

- Default conversion is direct second person: "How old is the \
applicant?" -> "How old are you?" — do this even with no other context \
to draw on.
- When the conversation says who the case is actually about (a parent \
asking for their child, someone asking on behalf of another person), \
use the pronoun/relationship that fits: "I need a passport for my \
daughter" + "How old is the applicant?" -> "How old is she?"
- Do not change what the question asks about, do not add information, \
do not ask a different or additional question, and do not state a fee, \
office, or requirement — rephrasing is wording only.

Examples:
- Recent message: "I want to renew my passport" / Canonical: "How old \
is the applicant?" -> "How old are you?"
- Recent message: "I need a passport for my daughter" / Canonical: \
"How old is the applicant?" -> "How old is she?" """


class Rephrasing(BaseModel):
    rephrased_text: str
    target_attribute: str


def _build_prompt(canonical_prompt: str, attribute: str, recent_turns: list[str]) -> str:
    context = "\n".join(truncate_message(turn) for turn in recent_turns) or "(no prior turns)"
    return (
        f"Recent conversation:\n{context}\n\n"
        f"Attribute to ask about: {attribute}\n"
        f"Canonical question: \"{canonical_prompt}\""
    )


def rephrase_question(canonical_prompt: str, attribute: str, recent_turns: list[str]) -> str:
    """Returns the rephrased question, or `canonical_prompt` unchanged on
    an attribute mismatch or any generation failure."""
    try:
        result = structured_completion(
            JOB,
            system=SYSTEM_PROMPT,
            user=_build_prompt(canonical_prompt, attribute, recent_turns),
            response_model=Rephrasing,
            max_tokens=MAX_TOKENS,
        )
    except Exception:
        # Any API failure, timeout, or malformed response — fall back to
        # the canonical prompt, no error surfaced to the citizen.
        return canonical_prompt

    if result.target_attribute != attribute:
        return canonical_prompt
    return result.rephrased_text
