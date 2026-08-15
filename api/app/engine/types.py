"""Shared result types returned by the engine's resolver functions.

Plain dataclasses, not ORM models — the engine returns citizen-facing
results, not database rows, so callers (tests today, API routes in
Phase 6) don't need a live session to read them.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class Citation:
    source_document_id: uuid.UUID
    source_url: str
    verified_at: datetime | None


@dataclass(frozen=True)
class ResolvedRequirement:
    id: uuid.UUID
    label: str
    kind: str  # document | step | prerequisite
    sequence: int
    citation: Citation


@dataclass(frozen=True)
class ResolvedFee:
    basis: str  # normal | urgent
    base_amount: float
    citation: Citation


@dataclass(frozen=True)
class ResolvedOffice:
    id: uuid.UUID
    name: str
    type: str  # head | regional | mission (never ds)


@dataclass(frozen=True)
class ConflictNote:
    note_text: str
    primary_citation: Citation
    secondary_citation: Citation | None


@dataclass(frozen=True)
class OfficeResolution:
    offices: list[ResolvedOffice]
    conflict_note: ConflictNote | None = None


@dataclass(frozen=True)
class AmendmentAlternative:
    fee: ResolvedFee
    requirements: list[ResolvedRequirement]


@dataclass(frozen=True)
class ScopeGateResponse:
    reason: str


@dataclass(frozen=True)
class CaseResolution:
    """The full result of resolving an adult renewal case.

    `scope_gate` is set (and every other field left empty/None) when the
    case falls outside this phase's scope (currently: under-16) — see
    the "under-16 case is scope-gated" spec requirement.
    """

    requirements: list[ResolvedRequirement] = field(default_factory=list)
    fee: ResolvedFee | None = None
    offices: OfficeResolution | None = None
    amendment_alternative: AmendmentAlternative | None = None
    scope_gate: ScopeGateResponse | None = None
