"""Shared question data for the renewal service's intake.

A single source of truth for (attribute, prompt, answer_type, sequence),
imported by both `app.seed.phase4_renewal` (which persists these as
`Question` rows) and `app.engine.next_question` (which needs to map a
persisted `Question` back to the semantic attribute the condition
evaluator and the golden test fixtures key answers by). `Question` itself
carries no attribute column — see design.md's "Condition.attribute names
the semantic fact" decision — so this module is what keeps seeding and
next-question logic from drifting apart on that mapping.
"""

# (attribute, prompt, answer_type, sequence)
RENEWAL_QUESTIONS: list[tuple[str, str, str, int]] = [
    ("age", "How old is the applicant?", "single", 1),
    (
        "holds_passport",
        "Do you still hold your current or a previous passport?",
        "boolean",
        2,
    ),
    (
        "name_changed",
        "Has your name changed since your passport was issued?",
        "boolean",
        3,
    ),
    ("dual_citizen", "Are you a dual citizen?", "boolean", 4),
    (
        "section_19_2",
        "Was your dual citizenship obtained under section 19(2) of the "
        "amended Citizenship Act 18 of 1948?",
        "boolean",
        5,
    ),
    (
        "profession",
        "What is your profession? (leave blank if not applicable)",
        "single",
        6,
    ),
    ("buddhist_priest", "Are you a Buddhist priest?", "boolean", 7),
    ("district", "Which district are you applying from?", "district", 8),
    (
        "service_basis",
        "Do you need normal or urgent (same-day) service?",
        "single",
        9,
    ),
]

ATTRIBUTE_BY_PROMPT: dict[str, str] = {
    prompt: attribute for attribute, prompt, _, _ in RENEWAL_QUESTIONS
}


def is_relevant(attribute: str, answers: dict[str, str]) -> bool:
    """Whether a question is still relevant given answers so far.

    Only `section_19_2` is conditionally relevant in this phase — it only
    matters once `dual_citizen` is known to be true. Every other renewal
    question is always relevant once reached in sequence.
    """
    if attribute == "section_19_2":
        return answers.get("dual_citizen") == "true"
    return True
