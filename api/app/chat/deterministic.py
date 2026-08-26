"""6.1 Deterministic first pass.

A per-attribute matcher table for the 10 renewal intake attributes (see
`app.engine.renewal_intake.RENEWAL_QUESTIONS`), keyed by `attribute` —
not `Question.answer_type` — because `answer_type="single"` covers
three different matching rules (numeric `age`, an enum-with-synonyms
`service_basis`, and always-accept `profession`); see design.md's
"Deterministic pass: a per-attribute matcher table, not a generic type
check" decision.

A message matches only when, after stripping surrounding whitespace, it
consists *solely* of a plausible answer token — a message with any
surrounding prose falls through to the Claude classifier (the
intent-classification spec's "message with surrounding prose" scenario).
`profession` is the one attribute that is always accepted as free text
(design.md), so any non-empty message answers it.

The district list mirrors what `app.seed.phase4_renewal` actually seeds
onto OFFICE.district (confirmed against the dev database) — all 25 Sri
Lankan districts, since between them the five Regional Offices cover
every district.
"""

from __future__ import annotations

DISTRICTS = [
    "Colombo",
    "Gampaha",
    "Kalutara",
    "Kandy",
    "Matale",
    "Nuwara Eliya",
    "Galle",
    "Matara",
    "Hambantota",
    "Jaffna",
    "Kilinochchi",
    "Mannar",
    "Vavuniya",
    "Mullaitivu",
    "Batticaloa",
    "Ampara",
    "Trincomalee",
    "Kurunegala",
    "Puttalam",
    "Anuradhapura",
    "Polonnaruwa",
    "Badulla",
    "Monaragala",
    "Ratnapura",
    "Kegalle",
]
_DISTRICT_BY_LOWER: dict[str, str] = {d.lower(): d for d in DISTRICTS}

# Bug fix (renewal re-verification, scenario 9 "Applying from abroad"):
# the district question has no valid answer for a citizen who isn't in
# Sri Lanka. The first fix matched abroad *phrases* directly against the
# district question, which was fragile — it recognized "abroad" and
# "overseas" but not "Dubai", "I live in Australia", or "UAE", so most
# real overseas citizens still got asked which Sri Lankan district
# they're in. The proper fix (per the Phase 9 proposal, now built) is a
# dedicated `applying_from` question asked BEFORE district
# (`app.engine.renewal_intake.RENEWAL_QUESTIONS`, sequence 8) with a
# closed sri_lanka/abroad answer — `district` is then skipped entirely
# for an abroad answer via a seeded `QUESTION_CONDITION`
# (`app.seed.phase4_renewal`), not asked at all, so there's no district
# text for a citizen abroad to mismatch against in the first place.
# Country names beyond the literal synonyms below (a "Dubai"/"Australia"
# answer to the applying_from question) fall through to the Gemini
# classifier, which is told to infer sri_lanka/abroad from a named
# location (`app.chat.classifier`), rather than hand-maintaining a
# country list here.
_SRI_LANKA_PHRASES = frozenset(
    {
        "sri lanka", "in sri lanka", "inside sri lanka", "domestic",
        "here", "local", "i'm in sri lanka", "im in sri lanka",
        "i am in sri lanka",
    }
)
_ABROAD_PHRASES = frozenset(
    {
        "abroad", "overseas", "not in sri lanka", "outside sri lanka",
        "i'm abroad", "im abroad", "i am abroad", "living abroad",
        "outside the country",
    }
)


def _match_applying_from(stripped_lower: str) -> str | None:
    if stripped_lower in _SRI_LANKA_PHRASES:
        return "sri_lanka"
    if stripped_lower in _ABROAD_PHRASES:
        return "abroad"
    return None


# passport-lost-stolen's own question — where the passport was lost/
# stolen (a fact about the past), distinct from `applying_from` (where
# the citizen is applying from now — see app.engine.renewal_intake's
# _LOST_LOCATION_QUESTION docstring for why these are separate
# attributes). Reuses the same core location words as
# _SRI_LANKA_PHRASES/_ABROAD_PHRASES (location-neutral either way) plus
# a few phrasings worded for "where it happened" rather than "where I
# am."
_LOST_IN_SRI_LANKA_PHRASES = _SRI_LANKA_PHRASES | frozenset(
    {"lost it here", "lost it in sri lanka", "it was lost here", "in the country"}
)
_LOST_ABROAD_PHRASES = _ABROAD_PHRASES | frozenset(
    {"lost it abroad", "lost it overseas", "it was lost abroad", "outside the country"}
)


def _match_lost_location(stripped_lower: str) -> str | None:
    if stripped_lower in _LOST_IN_SRI_LANKA_PHRASES:
        return "sri_lanka"
    if stripped_lower in _LOST_ABROAD_PHRASES:
        return "abroad"
    return None


BOOLEAN_ATTRIBUTES = frozenset(
    {"holds_passport", "name_changed", "dual_citizen", "section_19_2", "buddhist_priest"}
)

_YES_LEXICON = frozenset({"yes", "y", "yeah", "yep", "true", "correct"})
_NO_LEXICON = frozenset({"no", "n", "nope", "false", "incorrect"})

_SERVICE_BASIS_SYNONYMS: dict[str, str] = {
    "normal": "normal",
    "regular": "normal",
    "standard": "normal",
    "urgent": "urgent",
    "same-day": "urgent",
    "same day": "urgent",
    "expedited": "urgent",
    "rush": "urgent",
}

# passport-lost-stolen's own question (app.engine.renewal_intake.
# LOST_STOLEN_QUESTIONS) — selects the LKR 20,000/15,000 penalty tier
# (pages_e.php?id=8 seq 33-34).
_LOST_PASSPORT_WITHIN_1_YEAR_PHRASES = frozenset(
    {
        "within a year", "within the last year", "less than a year",
        "under a year", "within_1_year", "within 1 year",
    }
)
_LOST_PASSPORT_OVER_1_YEAR_PHRASES = frozenset(
    {
        "over a year", "more than a year", "more than a year ago",
        "over_1_year", "over 1 year", "longer than a year",
    }
)


def _match_age(stripped_lower: str) -> str | None:
    return stripped_lower if stripped_lower.isdigit() else None


def _match_service_basis(stripped_lower: str) -> str | None:
    return _SERVICE_BASIS_SYNONYMS.get(stripped_lower)


def _match_district(stripped_lower: str) -> str | None:
    return _DISTRICT_BY_LOWER.get(stripped_lower)


def _match_lost_passport_age(stripped_lower: str) -> str | None:
    if stripped_lower in _LOST_PASSPORT_WITHIN_1_YEAR_PHRASES:
        return "within_1_year"
    if stripped_lower in _LOST_PASSPORT_OVER_1_YEAR_PHRASES:
        return "over_1_year"
    return None


def _match_boolean(stripped_lower: str) -> str | None:
    if stripped_lower in _YES_LEXICON:
        return "true"
    if stripped_lower in _NO_LEXICON:
        return "false"
    return None


_MATCHERS = {
    "age": _match_age,
    "service_basis": _match_service_basis,
    "district": _match_district,
    "applying_from": _match_applying_from,
    "lost_location": _match_lost_location,
    "lost_passport_age": _match_lost_passport_age,
    **{attribute: _match_boolean for attribute in BOOLEAN_ATTRIBUTES},
}


# Bug fix (manual QA bug #3): "hi", "help", "passport" and close
# variants used to fall straight through to the pending-question
# matcher (never matches — "hi" isn't a plausible age/boolean/district
# token) and then to the Gemini classifier, which had nothing to extract
# and defaulted to intent="question" — producing "I don't have that
# information" plus an age question for what was actually a greeting or
# an orientation request, neither an answerable question nor a stated
# situation. Deliberately narrow: only the literal reported cases and
# their closest variants, checked as the ENTIRE stripped, lowercased
# message — "i need a passport" or "renew my passport" are real stated
# situations (CLAUDE.md's two-mechanism split) and must still start
# intake normally, not be swallowed here.
GREETING_PHRASES = frozenset(
    {
        "hi", "hello", "hey", "hiya", "yo", "good morning", "good afternoon", "good evening",
        "help", "help me", "menu", "start", "start over",
        "what can you do", "what is this", "what do you do", "who are you",
        "passport",
    }
)


def is_greeting(message: str) -> bool:
    return message.strip().lower() in GREETING_PHRASES


def try_deterministic_match(pending_attribute: str, message: str) -> str | None:
    """Return the normalized answer value when `message` is solely a
    plausible answer to `pending_attribute`, else None (falls through to
    the Claude classifier).

    `profession` always accepts any non-empty message, preserving its
    original casing/wording — free text is a valid profession answer by
    design, not just a bare token.
    """
    stripped = message.strip()

    if pending_attribute == "profession":
        # Bug fix (manual QA bug #4): the prompt itself says "leave
        # blank if you don't have one" — a blank message must record as
        # no profession ("", the same value BASE test fixtures already
        # use for "no profession"), not fall through to the classifier
        # (which has nothing to extract from empty text, so nothing gets
        # recorded and the same question — plus a spurious "I don't have
        # that information" — kept coming back). Checked before the
        # empty-message short-circuit below, which every other attribute
        # still hits.
        return stripped

    if not stripped:
        return None

    matcher = _MATCHERS.get(pending_attribute)
    if matcher is None:
        return None
    return matcher(stripped.lower())
