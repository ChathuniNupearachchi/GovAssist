"""Situation-to-service routing for a brand-new case's opening message.

Three services to route between: `passport-renewal` (the default),
`passport-new` (first-time applicant), `passport-lost-stolen` (a
previously-issued passport lost or stolen — design.md's own "Citizen's
words" for this service: "my passport was stolen", "I lost my
passport", "someone stole my bag with my passport in it").

Both design.md's service #2 and #3 flag the SAME misrouting risk from
opposite directions: a citizen whose passport merely expired,
described loosely as "I don't have a passport" or "I lost my passport"
(meaning "not currently, it lapsed" — not an actual loss/theft event),
should land on renewal, not first-time or lost-stolen. This module
doesn't attempt that finer distinction — a bare "i don't have a
passport" stays mapped to first-time (see FIRST_TIME_PHRASES), and
lost-stolen's own phrase set below is kept to unambiguous loss/theft
language ("stolen", "was lost" as an event, not "don't have") so the
two sets don't overlap. A genuinely ambiguous phrasing isn't in either
set and falls to the renewal default — the same "misroute costs a
label, not a wrong checklist" reasoning applies here too, though less
cleanly: unlike first-time (whose checklist converges with renewal's
once holds_passport is false), a genuine lost-stolen case misrouted to
renewal is missing the police-complaint prerequisite and the loss
penalty fee entirely — a real gap, not just a label/extra-question
issue, kept narrow specifically to minimize how often it happens rather
than accepted as costless.

Deliberately narrow and deterministic, same convention
`app.chat.deterministic.is_greeting`/`GREETING_PHRASES` already uses for
this kind of upfront routing decision: a small, explicit phrase set
matched against the ENTIRE stripped, lowercased opening message — no
free-text LLM classification, so no extra API call is added to a new
case's first turn (the existing `classify()` call inside the graph's
`classify` node still runs exactly once, unaffected by this).

A message that doesn't match falls back to `passport-renewal` — not a
wrong-checklist risk even when the "real" situation was first-time:
design.md's own service #2 record says fee/form/offices are "identical
to renewal," and a first-time citizen who lands on the renewal intake
still gets the right document set once `holds_passport` is answered
false (the existing current-passport condition already omits that item
correctly). A misroute here costs a mislabeled service and one
redundant `holds_passport` question, not an incorrect requirement — see
`app.engine.resolver.resolve_case`'s own `service_code` default for the
same reasoning from the other direction.
"""

from __future__ import annotations

from app.engine.resolver import (
    LOST_STOLEN_SERVICE_CODE,
    NEW_APPLICANT_SERVICE_CODE,
    RENEWAL_SERVICE_CODE,
)

# Design.md's own "Citizen's words" for service #2, plus the closest
# natural variants — checked as the entire stripped, lowercased message,
# same as GREETING_PHRASES, not a substring search (a substring match
# risks a false positive inside a longer, unrelated sentence this
# module was never meant to classify — free text should reach the
# classifier via the normal graph flow instead, this is a fast path for
# the unambiguous case only).
FIRST_TIME_PHRASES = frozenset(
    {
        "i've never had a passport",
        "ive never had a passport",
        "i have never had a passport",
        "i never had a passport",
        "applying for my first passport",
        "apply for my first passport",
        "i need my first passport",
        "i need a passport for the first time",
        "i want a passport for the first time",
        "getting a passport for the first time",
        "this is my first passport",
        "my first passport application",
        "i don't have a passport",
        "i dont have a passport",
        "i've never applied for a passport",
        "ive never applied for a passport",
        "i've never had a sri lankan passport",
        "ive never had a sri lankan passport",
    }
)


LOST_STOLEN_PHRASES = frozenset(
    {
        "my passport was stolen",
        "my passport got stolen",
        "someone stole my passport",
        "somebody stole my passport",
        "my passport was lost",
        "i lost my passport",
        "i've lost my passport",
        "ive lost my passport",
        "my passport is lost",
        "my passport is stolen",
        "someone stole my bag with my passport in it",
        "my bag with my passport was stolen",
        "my passport got lost",
    }
)


def route_opening_message(message: str) -> str:
    """Returns the service code a brand-new case's opening message
    should be attached to — `passport-new` for an unambiguous
    first-time phrasing, `passport-lost-stolen` for an unambiguous
    loss/theft phrasing, `passport-renewal` (the existing default)
    otherwise."""
    stripped_lower = message.strip().lower()
    if stripped_lower in FIRST_TIME_PHRASES:
        return NEW_APPLICANT_SERVICE_CODE
    if stripped_lower in LOST_STOLEN_PHRASES:
        return LOST_STOLEN_SERVICE_CODE
    return RENEWAL_SERVICE_CODE
