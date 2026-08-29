"""6.1 Deterministic first pass.

A per-attribute matcher table for every service's intake attributes
(see `app.engine.renewal_intake`), keyed by `attribute` — not
`Question.answer_type` — because `answer_type="single"` covers three
different matching rules (numeric `age`, an enum-with-synonyms
`service_basis`, and always-accept `profession`); see design.md's
"Deterministic pass: a per-attribute matcher table, not a generic type
check" decision.

CRITICAL BUG FIX (production incident — see this change's own report):
every matcher here used to require the ENTIRE stripped message to equal
a bare token ("20", "yes", "sri lanka") — a message with any
surrounding prose ("I am 20 years old") fell straight through to the
classifier, and a classifier failure/low-confidence result then
silently defaulted to routing the message to the full tool-agent as if
it were an unanswerable question, producing "I don't have that
information" and re-asking the same question forever. Every matcher
below now scans the WHOLE message for a plausible answer rather than
requiring the message to consist solely of one — this is what makes a
normal sentence answerable without ever needing an LLM call.

The district list mirrors what `app.seed.phase4_renewal` actually seeds
onto OFFICE.district (confirmed against the dev database) — all 25 Sri
Lankan districts, since between them the five Regional Offices cover
every district.
"""

from __future__ import annotations

import re

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
# Longest-first so "Nuwara Eliya" is tried before any single-word
# district that could theoretically be a substring of a longer name.
_DISTRICTS_BY_LEN_DESC = sorted(DISTRICTS, key=len, reverse=True)


def _flatten(message: str) -> str:
    """Lowercase, drop apostrophes (so "don't"/"I'm" collapse to
    "dont"/"im" — a single token matchable against a plain keyword
    rather than splitting into two on the removed punctuation), then
    replace every other non-alphanumeric character with a space and
    collapse whitespace. Tolerates missing/extra punctuation and the
    handful of contractions this domain's answers actually use."""
    text = message.strip().lower().replace("'", "").replace("’", "")
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _word_in(flat: str, phrase: str) -> bool:
    return re.search(rf"\b{re.escape(phrase)}\b", flat) is not None


# Bug found and fixed during this change's own live verification: the
# substring-based keyword matchers below (e.g. urgency's "urgent") are
# necessarily loose — but that means a genuine QUESTION that happens to
# mention the keyword ("what's the difference between normal and
# urgent?") would otherwise deterministically match as if it answered
# the pending question, skipping the classifier entirely and never
# reaching the agent that should actually answer it. Guarded globally,
# before any attribute-specific matcher runs, rather than patched into
# each matcher separately.
_QUESTION_STARTERS = frozenset(
    {
        "what", "whats", "which", "how", "why", "when", "where", "who", "whos",
        "is", "are", "do", "does", "did", "should", "would", "will", "can", "could",
    }
)


def _looks_like_a_question(original_stripped: str, flat: str) -> bool:
    if "?" in original_stripped:
        return True
    first_word = flat.split(" ", 1)[0] if flat else ""
    return first_word in _QUESTION_STARTERS


def _substr_in(flat: str, phrase: str) -> bool:
    """Plain substring test (no word-boundary requirement) — used for
    domain-specific roots like "urgent" that also need to match
    "urgently"/"urgency", where a false positive is effectively
    impossible in this narrow intake-answer context."""
    return phrase in flat


# ---- age ----


def _match_age(flat: str) -> str | None:
    """First number found anywhere in the message — "20", "I am 20",
    "im 20", "20 years old", "age 20", "i am 20 yrs" all reduce to the
    same extraction."""
    match = re.search(r"\d+", flat)
    return match.group(0) if match else None


# ---- boolean (yes/no) ----

BOOLEAN_ATTRIBUTES = frozenset(
    {
        "holds_passport", "name_changed", "dual_citizen", "section_19_2", "buddhist_priest",
        # passport-under-16 (design.md service #5) — see
        # app.engine.renewal_intake.UNDER_16_QUESTIONS.
        "parents_hold_passport", "child_previously_in_parent_passport",
        "child_adopted", "child_born_overseas",
    }
)

# Checked as whole tokens (after `_flatten` splits on whitespace) —
# short words like "no"/"not" would false-positive as substrings of
# unrelated words ("normal", "nothing"), so these need real boundaries,
# unlike the longer, more distinctive keyword sets below.
_NEGATIVE_TOKENS = frozenset(
    {
        "no", "nope", "not", "dont", "doesnt", "didnt", "cant", "cannot",
        "wont", "wouldnt", "havent", "hasnt", "isnt", "wasnt", "never", "nah",
    }
)
_POSITIVE_TOKENS = frozenset({"yes", "y", "yeah", "yep", "yup", "sure", "correct", "true", "affirmative"})
# Two-word affirmative phrases that don't reduce to a single token —
# "I do", "I have" (as in "yes I have it" already covered by the "yes"
# token, but a bare "I do"/"I have" with no "yes" at all still answers).
_POSITIVE_PHRASES = ("i do", "i have", "i still have", "still have it")


def _match_boolean(flat: str) -> str | None:
    tokens = flat.split()
    if any(token in _NEGATIVE_TOKENS for token in tokens):
        return "false"
    if any(token in _POSITIVE_TOKENS for token in tokens):
        return "true"
    if any(phrase in flat for phrase in _POSITIVE_PHRASES):
        return "true"
    return None


# ---- applying_from / lost_location (sri_lanka vs abroad) ----

# Country names beyond these literal phrases (a "Dubai"/"Australia"
# answer) fall through to the classifier, which is told to infer
# sri_lanka/abroad from a named location — hand-maintaining an
# exhaustive country/city list here would be a losing battle; the
# classifier (now Claude Haiku — see item 4 of this change) handles
# that generalization reliably instead.
_ABROAD_PHRASES = (
    "abroad", "overseas", "not in sri lanka", "outside sri lanka",
    "outside the country", "not in the country", "living abroad",
)
_SRI_LANKA_PHRASES = ("sri lanka", "domestic", "in the country", "here in", "locally")


def _match_location(flat: str) -> str | None:
    for phrase in _ABROAD_PHRASES:
        if phrase in flat:
            return "abroad"
    for phrase in _SRI_LANKA_PHRASES:
        if phrase in flat:
            return "sri_lanka"
    return None


def _match_applying_from(flat: str) -> str | None:
    return _match_location(flat)


def _match_lost_location(flat: str) -> str | None:
    return _match_location(flat)


# ---- district ----


def _match_district(flat: str) -> str | None:
    for district in _DISTRICTS_BY_LEN_DESC:
        if _word_in(flat, district.lower()):
            return district
    return None


# ---- urgency (service_basis) ----

_URGENT_KEYWORDS = ("urgent", "asap", "as soon as possible", "same day", "same-day", "rush", "expedite", "expedited")
_NORMAL_KEYWORDS = (
    "normal", "regular", "standard", "no rush", "not urgent", "not in a rush",
    "not in a hurry", "days is fine", "day is fine", "whenever", "no hurry",
)


def _match_service_basis(flat: str) -> str | None:
    for phrase in _URGENT_KEYWORDS:
        if _substr_in(flat, phrase):
            return "urgent"
    for phrase in _NORMAL_KEYWORDS:
        if _substr_in(flat, phrase):
            return "normal"
    return None


# ---- generic substring-over-synonyms matcher, for the remaining
# closed-vocabulary attributes below (alteration_type, validity_period,
# parent_circumstance, lost_passport_age) — same widening treatment:
# the phrase just needs to appear anywhere in the message, not be the
# entire message. Longest phrase checked first so a more specific
# synonym ("cancel india nepal only") wins over a shorter one it
# contains, where both happen to be present. ----


def _match_by_synonym_substring(flat: str, synonyms: dict[str, str]) -> str | None:
    for phrase in sorted(synonyms, key=len, reverse=True):
        if phrase in flat:
            return synonyms[phrase]
    return None


_ALTERATION_TYPE_SYNONYMS: dict[str, str] = {
    "change of name": "change_of_name",
    "name change": "change_of_name",
    "change my name": "change_of_name",
    "change my name on my passport": "change_of_name",
    "update my name": "change_of_name",
    "profession inclusion": "profession_inclusion",
    "add my profession": "profession_inclusion",
    "include my profession": "profession_inclusion",
    "add profession": "profession_inclusion",
    "nic inclusion": "nic_inclusion",
    "nic number inclusion": "nic_inclusion",
    "add my nic": "nic_inclusion",
    "add my nic number": "nic_inclusion",
    "include my nic number": "nic_inclusion",
    "cancel single journey": "cancel_single_journey",
    "cancel my single journey": "cancel_single_journey",
    "cancel india nepal": "cancel_india_nepal",
    "cancel india nepal only": "cancel_india_nepal",
    "cancel india/nepal": "cancel_india_nepal",
    "other": "other",
    "other amendment": "other",
    "something else": "other",
}

_VALIDITY_PERIOD_SYNONYMS: dict[str, str] = {
    "3 year": "3_year",
    "3-year": "3_year",
    "3 years": "3_year",
    "three year": "3_year",
    "three years": "3_year",
    "3_year": "3_year",
    "10 year": "10_year",
    "10-year": "10_year",
    "10 years": "10_year",
    "ten year": "10_year",
    "ten years": "10_year",
    "10_year": "10_year",
}

_PARENT_CIRCUMSTANCE_SYNONYMS: dict[str, str] = {
    "none": "none",
    "no": "none",
    "none of these": "none",
    "neither": "none",
    "n/a": "none",
    "deceased": "deceased",
    "dead": "deceased",
    "passed away": "deceased",
    "parent died": "deceased",
    "parent is deceased": "deceased",
    "divorced": "divorced",
    "parents divorced": "divorced",
    "parents are divorced": "divorced",
    "abandoned": "abandoned",
    "child was abandoned": "abandoned",
    "child abandoned": "abandoned",
}

_LOST_PASSPORT_AGE_SYNONYMS: dict[str, str] = {
    "within a year": "within_1_year",
    "within the last year": "within_1_year",
    "less than a year": "within_1_year",
    "under a year": "within_1_year",
    "within_1_year": "within_1_year",
    "within 1 year": "within_1_year",
    "over a year": "over_1_year",
    "more than a year": "over_1_year",
    "more than a year ago": "over_1_year",
    "over_1_year": "over_1_year",
    "over 1 year": "over_1_year",
    "longer than a year": "over_1_year",
}


def _match_alteration_type(flat: str) -> str | None:
    return _match_by_synonym_substring(flat, _ALTERATION_TYPE_SYNONYMS)


def _match_validity_period(flat: str) -> str | None:
    return _match_by_synonym_substring(flat, _VALIDITY_PERIOD_SYNONYMS)


def _match_parent_circumstance(flat: str) -> str | None:
    return _match_by_synonym_substring(flat, _PARENT_CIRCUMSTANCE_SYNONYMS)


def _match_lost_passport_age(flat: str) -> str | None:
    return _match_by_synonym_substring(flat, _LOST_PASSPORT_AGE_SYNONYMS)


_MATCHERS = {
    "age": _match_age,
    "service_basis": _match_service_basis,
    "district": _match_district,
    # Same district vocabulary and validation as `district` — a
    # separate attribute (item 5 of the intake-parsing fix), not a
    # separate matching rule. The "same as my applying district"
    # shortcut (a bare "same"/"yes") is handled in
    # app.graph.nodes.classify_node, which has access to the case's
    # already-recorded `district` answer; this matcher only ever
    # resolves an explicitly-named district.
    "photo_district": _match_district,
    "applying_from": _match_applying_from,
    "lost_location": _match_lost_location,
    "lost_passport_age": _match_lost_passport_age,
    "alteration_type": _match_alteration_type,
    "validity_period": _match_validity_period,
    "parent_circumstance": _match_parent_circumstance,
    **{attribute: _match_boolean for attribute in BOOLEAN_ATTRIBUTES},
}

# profession's own not-applicable vocabulary — checked as the ENTIRE
# flattened message (not a substring — "I have no job title I want to
# list" is a real profession-adjacent statement, not a not-applicable
# marker, so this stays narrow and exact).
#
# BUG FIX (conversational-quality round, item 4): a 15-year-old
# answering "student" (a legitimate, common answer to "what is your
# job or occupation?" for a minor) was being recorded as their literal
# profession — a non-empty string, which incorrectly triggered the
# educational/service certificate requirement (a document meant for an
# ADULT's stated occupation, not "I am currently in school"). Widened
# considerably; still whole-message exact matches only, not a blanket
# substring search, for the same false-positive reason as above.
_PROFESSION_NOT_APPLICABLE = frozenset(
    {
        "none", "no job", "n a", "na", "n/a", "no profession", "unemployed", "nothing",
        "not applicable", "student", "a student", "im a student", "still a student",
        "school student", "none yet", "no occupation", "not employed", "no employment",
        "not working", "dont work", "do not work", "no current job", "currently unemployed",
        "not currently employed", "still studying", "still in school",
    }
)

# Same not-applicable meaning, but as a phrase that can appear WITHIN a
# longer sentence rather than being the entire message — a small,
# hand-picked set of near-unambiguous negative-employment fragments
# (never a bare word like "job" or "student" alone, which the exact-
# match set above already covers for the bare-word case and which as a
# raw substring would risk exactly the false positive the module
# docstring above warns about).
_PROFESSION_NOT_APPLICABLE_FRAGMENTS = (
    "dont have a job", "do not have a job", "dont have a profession",
    "do not have a profession", "no job yet", "im a student", "i am a student",
    "im unemployed", "i am unemployed", "dont currently work", "do not currently work",
)

# Bug fix (manual QA bug #3): "hi", "help", "passport" and close
# variants used to fall straight through to the pending-question
# matcher (never matches — "hi" isn't a plausible age/boolean/district
# token) and then to the classifier, which had nothing to extract and
# defaulted to intent="question" — producing "I don't have that
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


# photo_district's "default to my applying district" shortcut (item 5
# of the intake-parsing fix) — a bare affirmation meaning "yes, the
# same district I already gave," resolved in app.graph.nodes.
# classify_node (which has the case's already-recorded `district`
# answer; this module has no access to prior answers).
_SAME_AS_BEFORE_PHRASES = frozenset(
    {"same", "yes", "yeah", "yep", "same one", "same as before", "same district", "there too", "here too"}
)


def is_same_district_as_before(message: str) -> bool:
    return _flatten(message) in _SAME_AS_BEFORE_PHRASES


def try_deterministic_match(pending_attribute: str, message: str) -> str | None:
    """Return the normalized answer value when `message` plausibly
    answers `pending_attribute` — anywhere within the message, not only
    as a bare token — else None (falls through to the classifier).

    `profession` always accepts any non-empty message, preserving its
    original casing/wording — free text is a valid profession answer by
    design, not just a bare token. A not-applicable reply ("none", "no
    job", blank) records as "" rather than that literal text, matching
    the existing "no profession" convention.
    """
    stripped = message.strip()

    if pending_attribute == "profession":
        flat = _flatten(stripped)
        if not stripped or flat in _PROFESSION_NOT_APPLICABLE:
            return ""
        if any(fragment in flat for fragment in _PROFESSION_NOT_APPLICABLE_FRAGMENTS):
            return ""
        if _looks_like_a_question(stripped, flat):
            return None
        return stripped

    if not stripped:
        return None

    flat = _flatten(stripped)
    if _looks_like_a_question(stripped, flat):
        return None

    matcher = _MATCHERS.get(pending_attribute)
    if matcher is None:
        return None
    return matcher(flat)
