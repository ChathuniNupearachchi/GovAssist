"""6.1 Deterministic first pass.

A per-attribute matcher table for the 9 renewal intake attributes (see
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


def _match_age(stripped_lower: str) -> str | None:
    return stripped_lower if stripped_lower.isdigit() else None


def _match_service_basis(stripped_lower: str) -> str | None:
    return _SERVICE_BASIS_SYNONYMS.get(stripped_lower)


def _match_district(stripped_lower: str) -> str | None:
    return _DISTRICT_BY_LOWER.get(stripped_lower)


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
    **{attribute: _match_boolean for attribute in BOOLEAN_ATTRIBUTES},
}


def try_deterministic_match(pending_attribute: str, message: str) -> str | None:
    """Return the normalized answer value when `message` is solely a
    plausible answer to `pending_attribute`, else None (falls through to
    the Claude classifier).

    `profession` always accepts any non-empty message, preserving its
    original casing/wording — free text is a valid profession answer by
    design, not just a bare token.
    """
    stripped = message.strip()
    if not stripped:
        return None

    if pending_attribute == "profession":
        return stripped

    matcher = _MATCHERS.get(pending_attribute)
    if matcher is None:
        return None
    return matcher(stripped.lower())
