"""4.4 Office resolver.

Precedence (stated, deterministic — see design.md's "Office resolver
precedence"):
1. Head Office is always in the accepting list, regardless of district.
   Divisional Secretariats are never queried at all — they distribute
   application forms, not a place submission is accepted, and are
   excluded by construction (this resolver never selects `type=ds`).
2. Regional Offices are narrowed to the one(s) whose `district` array
   contains the citizen's answered district; if no district is known yet,
   all Regional Offices are listed.
3. Missions are included ONLY when no district is known — a domestic
   applicant who has stated a Sri Lankan district is never shown Overseas
   Missions (bug fix: this resolver used to include every Mission
   unconditionally, regardless of district — a Colombo applicant was
   shown "Overseas Sri Lankan Missions" alongside a domestic regional
   office, which is wrong; Missions serve applicants applying from
   abroad, not a domestic applicant who merely hasn't stated urgency).
   This is a stand-in for a real "applying from abroad" signal, which
   the intake does not yet ask for separately — an unknown district is
   the closest available proxy for "not yet known to be domestic," and a
   known Sri Lankan district is conclusive proof the applicant is not
   applying from abroad.
4. On `basis="urgent"`, the seeded `urgent_office_conflict`
   ResolutionNote is attached — offices are never removed for it, the
   conflict is "confirm before traveling," not an exclusion.
5. Fixed output order: Head Office, then Regional Office(s)
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
    db: Session, district: str | None, basis: str
) -> OfficeResolution:
    head = db.scalars(
        select(Office).where(Office.type == "head").order_by(Office.name)
    ).all()

    regional = db.scalars(
        select(Office).where(Office.type == "regional").order_by(Office.name)
    ).all()
    if district:
        regional = [
            o for o in regional if o.district and district in o.district
        ]

    # Missions only when district is unknown — see the module docstring's
    # step 3. A known Sri Lankan district rules out "applying from
    # abroad," so Missions are never shown to a domestic applicant.
    missions = (
        []
        if district
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
