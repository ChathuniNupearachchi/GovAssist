"""Situation-to-service routing for a brand-new case's opening message.

Seven services to route between: `passport-renewal` (the default),
`passport-new` (first-time applicant), `passport-lost-stolen` (a
previously-issued passport lost or stolen — design.md's own "Citizen's
words" for this service: "my passport was stolen", "I lost my
passport", "someone stole my bag with my passport in it"),
`passport-amendment` (design.md's own "Citizen's words": "I need to
change my name on my passport", "add my profession to my passport",
"update my NIC number on my passport" — the citizen already holds the
passport, wants to change data on it, not replace it),
`passport-under-16` (design.md's own "Citizen's words": "applying for
my child's first passport", "my son needs a passport", "how do I get a
passport for my daughter" — service #5's own "Common misrouting" note:
a parent asking to "add"/"include" their child on their own passport
is a real, commonly-asked question, not a routable situation — that's
no longer offered at all (id=8 seq 30: "Inclusion of children in
parent passports will not longer be allowed"), so it should reach the
open-question path and be told so directly, not silently routed
anywhere; this module doesn't special-case that phrasing at all,
leaving it to fall through to the classifier as an ordinary message),
`passport-child-deletion` (design.md's own "Citizen's words": "remove
my child from my passport", "I need to take my daughter off my
passport", "my son needs his own passport now, how do I delete him
from mine" — kept as its OWN phrase set distinct from AMENDMENT_PHRASES
per service #6's own "Common misrouting" note: a parent might describe
this generically as "an amendment" without realizing it's its own
errand, which is exactly why this module routes an unambiguous
"remove"/"delete [a child]" phrasing straight here rather than to
amendment first), `emergency-certificate` (design.md's own "Citizen's
words": "I need an emergency certificate for Nepal", "going to India on
pilgrimage, what travel document do I need" — service #7's own "Common
misrouting" note flags this the other direction too: a citizen wanting
a full ordinary passport for India/Nepal travel might not realize this
narrower, cheaper document exists — this module can't fix that (it only
routes an already-stated intent, it doesn't suggest alternatives), but
an unambiguous "emergency certificate"/pilgrimage phrasing is routed
straight here rather than falling to the renewal default).

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
    AMENDMENT_SERVICE_CODE,
    CHILD_DELETION_SERVICE_CODE,
    EMERGENCY_CERTIFICATE_SERVICE_CODE,
    LOST_STOLEN_SERVICE_CODE,
    NEW_APPLICANT_SERVICE_CODE,
    RENEWAL_SERVICE_CODE,
    UNDER_16_SERVICE_CODE,
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


AMENDMENT_PHRASES = frozenset(
    {
        "i need to change my name on my passport",
        "i want to change my name on my passport",
        "change my name on my passport",
        "add my profession to my passport",
        "include my profession on my passport",
        "update my nic number on my passport",
        "add my nic number to my passport",
        "i want to amend my passport",
        "i need to amend my passport",
        "amend my passport",
        "i need to correct my passport",
        "correct my passport details",
    }
)


UNDER_16_PHRASES = frozenset(
    {
        "applying for my child's first passport",
        "applying for my childs first passport",
        "my child needs a passport",
        "my son needs a passport",
        "my daughter needs a passport",
        "how do i get a passport for my daughter",
        "how do i get a passport for my son",
        "how do i get a passport for my child",
        "i need a passport for my child",
        "i need a passport for my son",
        "i need a passport for my daughter",
        "passport for my child",
        "passport for my son",
        "passport for my daughter",
        "my child's first passport",
        "my childs first passport",
    }
)


CHILD_DELETION_PHRASES = frozenset(
    {
        "remove my child from my passport",
        "i need to remove my child from my passport",
        "take my daughter off my passport",
        "i need to take my daughter off my passport",
        "take my son off my passport",
        "i need to take my son off my passport",
        "delete my child from my passport",
        "delete my son from my passport",
        "delete my daughter from my passport",
        "how do i delete my child from my passport",
        "how do i remove my child from my passport",
        "remove my daughter from my passport",
        "remove my son from my passport",
    }
)


EMERGENCY_CERTIFICATE_PHRASES = frozenset(
    {
        "i need an emergency certificate",
        "i need an emergency certificate for nepal",
        "i need an emergency certificate for india",
        "i need an emergency certificate for india or nepal",
        "going to india on pilgrimage, what travel document do i need",
        "going to nepal on pilgrimage, what travel document do i need",
        "i need an emergency certificate for my pilgrimage",
        "emergency certificate for india and nepal",
        "how do i get an emergency certificate",
        "i'm going on a buddhist pilgrimage to india",
        "im going on a buddhist pilgrimage to india",
        "i'm going on a buddhist pilgrimage to nepal",
        "im going on a buddhist pilgrimage to nepal",
    }
)


def route_opening_message(message: str) -> str:
    """Returns the service code a brand-new case's opening message
    should be attached to — `passport-new` for an unambiguous
    first-time phrasing, `passport-lost-stolen` for an unambiguous
    loss/theft phrasing, `passport-amendment` for an unambiguous
    change-existing-data phrasing, `passport-under-16` for an
    unambiguous child's-passport phrasing, `passport-child-deletion`
    for an unambiguous remove-a-child phrasing, `emergency-certificate`
    for an unambiguous Emergency Certificate/pilgrimage phrasing,
    `passport-renewal` (the existing default) otherwise. Child-deletion
    is checked BEFORE amendment — a phrase like "remove my child from
    my passport" is unambiguous for deletion specifically, so it's
    matched there first rather than risking AMENDMENT_PHRASES catching
    a stray substring."""
    stripped_lower = message.strip().lower()
    if stripped_lower in FIRST_TIME_PHRASES:
        return NEW_APPLICANT_SERVICE_CODE
    if stripped_lower in LOST_STOLEN_PHRASES:
        return LOST_STOLEN_SERVICE_CODE
    if stripped_lower in CHILD_DELETION_PHRASES:
        return CHILD_DELETION_SERVICE_CODE
    if stripped_lower in AMENDMENT_PHRASES:
        return AMENDMENT_SERVICE_CODE
    if stripped_lower in UNDER_16_PHRASES:
        return UNDER_16_SERVICE_CODE
    if stripped_lower in EMERGENCY_CERTIFICATE_PHRASES:
        return EMERGENCY_CERTIFICATE_SERVICE_CODE
    return RENEWAL_SERVICE_CODE
