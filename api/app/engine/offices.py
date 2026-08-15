"""4.4 Office resolver.

Precedence (stated, deterministic — see design.md's "Office resolver
precedence"):
1. Head Office and Missions are always in the accepting list, regardless
   of district. Divisional Secretariats are never queried at all — they
   distribute application forms, not a place submission is accepted, and
   are excluded by construction (this resolver never selects `type=ds`).
2. Regional Offices are narrowed to the one(s) whose `district` array
   contains the citizen's answered district; if no district is known yet,
   all Regional Offices are listed.
3. On `basis="urgent"`, the seeded `urgent_office_conflict`
   ResolutionNote is attached — offices are never removed for it, the
   conflict is "confirm before traveling," not an exclusion.
4. Fixed output order: Head Office, then Regional Office(s)
   (alphabetical), then Missions (alphabetical) — never dependent on
   unordered set/dict iteration, so repeated calls are identical.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.engine.types import Citation, ConflictNote, OfficeResolution, ResolvedOffice
from app.models import Office, ResolutionNote

URGENT_CONFLICT_NOTE_CODE = "urgent_office_conflict"


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

    missions = db.scalars(
        select(Office).where(Office.type == "mission").order_by(Office.name)
    ).all()

    offices = [_to_resolved(o) for o in (*head, *regional, *missions)]

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

    return OfficeResolution(offices=offices, conflict_note=conflict_note)
