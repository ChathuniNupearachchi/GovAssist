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
    # Downloadable resources (e.g. a form PDF and its filling
    # instructions) — a list of {"label", "url", "type"} dicts, or None
    # for a requirement with none. Structured so a client can render
    # tappable download links rather than a URL buried in prose — see
    # case-resolution-data-model's "requirement resources" requirement.
    resources: list[dict] | None = None


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
class ResolvedStudio:
    id: uuid.UUID
    name: str
    address: str
    phone: str | None
    citation: Citation


@dataclass(frozen=True)
class StudioResolution:
    district: str
    studios: list[ResolvedStudio]
    # Always present — the studio acknowledgement/receipt-submission
    # note applies regardless of which studio the citizen chose. See
    # app.engine.studios.RECEIPT_NOTE.
    receipt_note: str


@dataclass(frozen=True)
class ConflictNote:
    note_text: str
    primary_citation: Citation
    secondary_citation: Citation | None


@dataclass(frozen=True)
class OfficeResolution:
    offices: list[ResolvedOffice]
    conflict_note: ConflictNote | None = None
    # Set whenever a specific district narrowed the regional office list
    # (never set when district is unknown and every regional office is
    # listed) — the Phase 2 district-to-office mapping was recorded as a
    # geographic placeholder, never verified against the Department's own
    # jurisdiction data (no such data is published). Presented alongside
    # the offices, not asserted away, per the office-resolver bug fix's
    # explicit instruction not to claim an office is "nearest."
    district_mapping_caveat: str | None = None


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


class IncompleteCaseError(Exception):
    """Raised by `resolve_case` when a relevant renewal question has not
    yet been answered.

    A gating condition treats a missing answer as "not satisfied"
    regardless of negation (`app.engine.conditions.condition_link_passes`),
    which means a requirement set built from partial answers is not
    "everything not yet known to apply" — it silently omits branches that
    depend on the missing fact in either direction. An unanswered
    `dual_citizen`, for example, suppresses both the standard document
    set (gated on `dual_citizen != true`) and the dual-citizen set
    (gated on `dual_citizen == true`) at once. A resolver that returned
    that partial set as if it were the plan would be indistinguishable
    from a citizen's actual, complete checklist — an empty-looking gap
    is more dangerous than an explicit refusal, because it reads as
    "done" rather than "incomplete". `resolve_case` refuses instead: it
    raises this exception rather than returning a plausible-looking but
    silently partial `CaseResolution`.
    """

    def __init__(self, pending_prompt: str):
        self.pending_prompt = pending_prompt
        super().__init__(
            f"Case is not ready to resolve — still pending: {pending_prompt}"
        )
