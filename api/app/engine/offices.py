"""4.4 Office resolver.

Precedence (stated, deterministic — see design.md's "Office resolver
precedence"):
0. `applying_from` ("sri_lanka" | "abroad", from the intake's own
   dedicated question — `app.engine.renewal_intake`) is the PRIMARY
   routing signal. "abroad" routes entirely to the Mission path (id=9)
   below, skipping every other rule in this list. `district` alone is
   kept ONLY as a defensive fallback for a caller that doesn't pass
   `applying_from` (bug fix history: an unknown/empty district used to
   be the *only* signal for "applying from abroad," which meant any
   free-text answer other than an exact district name — "Dubai",
   "Australia", "I live in the UAE" — silently mismatched instead of
   being recognized as abroad; it also meant a "sri_lanka" answer with a
   temporarily-missing district could be confused with "abroad" — see
   below).
1. Mission path (`applying_from == "abroad"`): the accepting office is
   the Overseas Sri Lankan Mission only. id=9 seq 2: applications from
   abroad go "through the Sri Lankan Mission in that country" — never a
   domestic Head or Regional Office, and no district is asked at all
   (`app.seed.phase4_renewal`'s `QUESTION_CONDITION` on the district
   question). Head Office is excluded even though id=9 notes Mission
   submissions are administratively processed there — that isn't a
   citizen-facing submission point.
2. Domestic path (`applying_from == "sri_lanka"`, or the defensive
   fallback below): Head Office is always in the accepting list,
   regardless of district. Divisional Secretariats are never queried at
   all — they distribute application forms, not a place submission is
   accepted, and are excluded by construction (this resolver never
   selects `type=ds`).
3. Regional Offices are narrowed to the one(s) whose `district` array
   contains the citizen's answered district; if no district is known yet,
   all Regional Offices are listed.
4. Missions are included in the domestic path ONLY when `applying_from`
   is neither "sri_lanka" nor "abroad" (i.e. not recorded at all — the
   defensive fallback) AND no district is known either — a domestic
   applicant who has stated "sri_lanka" or a Sri Lankan district is
   never shown Overseas Missions (bug fix: this resolver used to include
   every Mission unconditionally, regardless of district — a Colombo
   applicant was shown "Overseas Sri Lankan Missions" alongside a
   domestic regional office, which is wrong).
5. On `basis="urgent"`, the seeded `urgent_office_conflict`
   ResolutionNote is attached in the domestic path only — the conflict
   text is about Head Office vs. Regional Office urgent-service hours,
   which doesn't apply once the only accepting office is a Mission.
   Offices are never removed for it, the conflict is "confirm before
   traveling," not an exclusion.
6. Fixed output order: Head Office, then Regional Office(s)
   (alphabetical), then Missions (alphabetical) — never dependent on
   unordered set/dict iteration, so repeated calls are identical.

The regional office narrowing itself (step 2) is **not** verified
against any published departmental jurisdiction data — the Department's
site does not publish which of the 5 Regional Offices serves which of
the 25 districts. The Phase 2 district-to-office mapping was recorded as
a geographic placeholder needing verification (see design.md), so this
resolver never asserts an office is "nearest" or "correct" for a
district — see `district_mapping_caveat` below, always set whenever
district-based narrowing actually happened.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.engine.types import Citation, ConflictNote, OfficeResolution, ResolvedOffice
from app.models import Office, ResolutionNote

URGENT_CONFLICT_NOTE_CODE = "urgent_office_conflict"

DISTRICT_MAPPING_CAVEAT = (
    "The district-to-office mapping used here is a placeholder recorded "
    "during initial data entry and has not been verified against the "
    "Department's own jurisdiction data (the Department does not publish "
    "which Regional Office serves which district). If in doubt, confirm "
    "with the listed office directly, or use the Head Office."
)


def _to_resolved(office: Office) -> ResolvedOffice:
    return ResolvedOffice(id=office.id, name=office.name, type=office.type)


def resolve_offices(
    db: Session, district: str | None, basis: str, applying_from: str | None = None
) -> OfficeResolution:
    """`applying_from` ("sri_lanka" | "abroad", from the intake's own
    question — `app.engine.renewal_intake`) is the PRIMARY signal for
    which office(s) accept the application, per the module docstring's
    step 3. `district` alone is a defensive fallback for a caller that
    doesn't pass `applying_from` at all (e.g. a legacy direct
    `resolve_case` call, or `app.chat.tools.find_office`'s open-question
    tool, which doesn't ask this question) — an empty/unknown district
    is treated as "not yet known to be domestic," same as before this
    question existed, but is no longer how a stated "abroad" answer gets
    detected."""
    head = db.scalars(
        select(Office).where(Office.type == "head").order_by(Office.name)
    ).all()

    regional = db.scalars(
        select(Office).where(Office.type == "regional").order_by(Office.name)
    ).all()

    if applying_from == "abroad":
        # Mission path (id=9 seq 2): "A Sri Lankan citizen can apply...
        # while he is in another country, through the Sri Lankan Mission
        # in that country" — submission happens at the Mission, never at
        # a domestic Head or Regional Office (those only accept
        # in-person domestic submission). id=9 also notes Missions
        # submissions are administratively processed at the Head Office,
        # but that isn't a citizen-facing submission point, so Head
        # Office is excluded here too — CLAUDE.md's "the specific office
        # that accepts their application" is the Mission, not Head
        # Office, for this branch.
        missions = db.scalars(
            select(Office).where(Office.type == "mission").order_by(Office.name)
        ).all()
        offices = [_to_resolved(o) for o in missions]
        return OfficeResolution(offices=offices, conflict_note=None)

    if district:
        regional = [
            o for o in regional if o.district and district in o.district
        ]

    # Missions only when the citizen isn't affirmatively known to be
    # domestic AND no district was even given — the defensive fallback
    # above. A "sri_lanka" answer with a temporarily-missing district
    # (an edge case `resolve_case`'s own intake-completeness check
    # should prevent in practice) never shows Missions, same as a known
    # district would — see the module docstring's step 3.
    missions = (
        []
        if applying_from == "sri_lanka" or district
        else db.scalars(
            select(Office).where(Office.type == "mission").order_by(Office.name)
        ).all()
    )

    offices = [_to_resolved(o) for o in (*head, *regional, *missions)]
    district_mapping_caveat = DISTRICT_MAPPING_CAVEAT if district else None

    conflict_note = None
    if basis == "urgent":
        note = db.scalars(
            select(ResolutionNote).where(
                ResolutionNote.code == URGENT_CONFLICT_NOTE_CODE
            )
        ).first()
        if note is not None:
            primary = note.primary_source_document
            secondary = note.secondary_source_document
            conflict_note = ConflictNote(
                note_text=note.note_text,
                primary_citation=Citation(
                    source_document_id=primary.id,
                    source_url=primary.source_url,
                    verified_at=None,
                ),
                secondary_citation=(
                    Citation(
                        source_document_id=secondary.id,
                        source_url=secondary.source_url,
                        verified_at=None,
                    )
                    if secondary is not None
                    else None
                ),
            )

    return OfficeResolution(
        offices=offices,
        conflict_note=conflict_note,
        district_mapping_caveat=district_mapping_caveat,
    )
