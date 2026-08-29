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
a Sri Lankan citizen using a passport-service chat assistant, given the \
canonical question, the attribute it asks about, and the last couple of \
turns of conversation (including the citizen's most recent message).

ALWAYS rewrite it into short, warm, first/second-person conversational \
phrasing — never return the canonical wording unchanged. The canonical \
prompts are written in bureaucratic third person ("How old is the \
applicant?", "Do you still hold your current or a previous passport?") \
precisely because they're the system's internal record, not what a \
citizen should read; your job is to convert that into how a helpful \
person would actually ask it out loud — a person having a conversation, \
not a form being administered — every single time, not only when the \
conversation gives you an obvious hook.

- Default conversion is direct second person: "How old is the \
applicant?" -> "How old are you?" — do this even with no other context \
to draw on.
- When the conversation says who the case is actually about (a parent \
asking for their child, someone asking on behalf of another person), \
use the pronoun/relationship that fits: "I need a passport for my \
daughter" + "How old is the applicant?" -> "How old is she?"
- CONVERSATIONAL-QUALITY FIX: when the case is about a CHILD, "you" \
always means the PARENT you are actually talking to — never reuse "you" \
for a question that is genuinely about the child (that's "her"/"him"/ \
"your daughter"/etc, per the rule above), and never say "your parents" \
for a question about the CHILD's parents (that means the citizen \
themselves and the other parent, not the citizen's own parents/the \
child's grandparents) — say "the child's parents" or "both parents" \
instead. A live bug this fixes: "Do both parents currently hold a \
valid Sri Lankan passport?" was being rephrased as "Do both of YOUR \
parents..." to a parent chatting about their child — confusingly asking \
about the child's grandparents. Correct: "Do you and the child's other \
parent both currently hold a valid Sri Lankan passport?" or "Do both of \
the child's parents currently hold a valid Sri Lankan passport?".
- Do not change what the question asks about, do not add information, \
do not ask a different or additional question, and do not state a fee, \
office, or requirement — rephrasing is wording only.
- When told this is the VERY FIRST question of the conversation, open \
with one brief, warm sentence naming what you're helping with — inferred \
from the citizen's own opening message — before asking the question. \
Keep the framing sentence short; do not repeat it on any later question \
(you'll be told explicitly when a question is NOT the first one — on \
those, just ask the question directly, no framing).

Examples:
- Recent message: "I want to renew my passport" / Canonical: "How old \
is the applicant?" (first question) -> "I can help you renew your \
passport. To start, how old are you?"
- Recent message: "I need a passport for my daughter" / Canonical: \
"How old is the applicant?" (first question) -> "I can help with that. \
To start, how old is she?"
- Recent message: "30" / Canonical: "Are you applying from inside Sri \
Lanka, or from abroad?" (not the first question) -> "Are you applying \
from inside Sri Lanka, or from abroad?"
- Recent message: "my child needs a passport" (a few turns into a \
child's-passport conversation) / Canonical: "Do both parents currently \
hold a valid Sri Lankan passport?" (not the first question) -> "Do you \
and the child's other parent both currently hold a valid Sri Lankan \
passport?" """


class Rephrasing(BaseModel):
    rephrased_text: str
    target_attribute: str


def _build_prompt(canonical_prompt: str, attribute: str, recent_turns: list[str]) -> str:
    context = "\n".join(truncate_message(turn) for turn in recent_turns) or "(no prior turns)"
    # Item 6 of the intake-parsing fix: "the very first question" is
    # detectable structurally, not guessed by the model — `recent_turns`
    # is prior transcript messages plus the citizen's current one
    # (`app.graph.build._recent_turn_contents`), so a length of 1 means
    # there is no prior turn at all, i.e. this literally is turn one.
    position_note = (
        "This is the VERY FIRST question of the conversation — the "
        "citizen has not been asked anything yet."
        if len(recent_turns) <= 1
        else "This is NOT the first question — a framing sentence has "
        "already been given earlier in this conversation; do not repeat one."
    )
    return (
        f"{position_note}\n\n"
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
