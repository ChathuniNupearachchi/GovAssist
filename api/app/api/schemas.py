"""5.5 Pydantic response models.

Built field-by-field from `app.engine.types` / `app.rag` dataclasses,
not by making those dataclasses themselves Pydantic models — keeps the
engine and RAG packages framework-agnostic, consistent with their
Phase 4/5 "build and test in isolation" design (design.md's "FastAPI
structure" decision).

Every model carrying a requirement, fee, or office includes its
citation fields, per the case-api spec's "Every requirement, fee, or
office in a response carries its citation" requirement.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.engine import types as engine_types
from app.rag.answer import RAGResponse


class CitationOut(BaseModel):
    source_document_id: uuid.UUID
    source_url: str
    verified_at: datetime | None

    @classmethod
    def from_citation(cls, citation: engine_types.Citation) -> "CitationOut":
        return cls(
            source_document_id=citation.source_document_id,
            source_url=citation.source_url,
            verified_at=citation.verified_at,
        )


class ResourceOut(BaseModel):
    label: str
    url: str
    type: str


class RequirementOut(BaseModel):
    id: uuid.UUID
    label: str
    kind: str
    sequence: int
    citation: CitationOut
    # Downloadable resources (e.g. a form PDF and its filling
    # instructions) as structured, tappable links — never embedded only
    # in prose. Empty list when a requirement has none.
    resources: list[ResourceOut] = []

    @classmethod
    def from_resolved(cls, r: engine_types.ResolvedRequirement) -> "RequirementOut":
        return cls(
            id=r.id,
            label=r.label,
            kind=r.kind,
            sequence=r.sequence,
            citation=CitationOut.from_citation(r.citation),
            resources=[ResourceOut(**res) for res in (r.resources or [])],
        )


class FeeOut(BaseModel):
    basis: str
    base_amount: float
    # Seven-corrections round, item 5 — "LKR" for every fee this app
    # quoted before this fix; a genuinely different currency (USD, for
    # an overseas applicant's fee, per the circular) from here on. Any
    # client rendering a fee must read this field, not assume LKR.
    currency: str
    # Conversational-quality round, item 6's own demo-scenario finding
    # — non-null only for a lost/stolen case with a penalty tier
    # applied. `base_amount` is always the genuine base fee alone; a
    # citizen-facing total is `base_amount + (penalty_amount or 0)`,
    # computed by whoever renders it (never pre-summed server-side) so
    # the breakdown itself is always visible, not folded into one
    # unexplained number.
    penalty_amount: float | None
    citation: CitationOut

    @classmethod
    def from_resolved(cls, f: engine_types.ResolvedFee) -> "FeeOut":
        return cls(
            basis=f.basis,
            base_amount=float(f.base_amount),
            currency=f.currency,
            penalty_amount=float(f.penalty_amount) if f.penalty_amount is not None else None,
            citation=CitationOut.from_citation(f.citation),
        )


class OfficeOut(BaseModel):
    id: uuid.UUID
    name: str
    type: str

    @classmethod
    def from_resolved(cls, o: engine_types.ResolvedOffice) -> "OfficeOut":
        return cls(id=o.id, name=o.name, type=o.type)


class ConflictNoteOut(BaseModel):
    note_text: str
    primary_citation: CitationOut
    secondary_citation: CitationOut | None

    @classmethod
    def from_resolved(cls, n: engine_types.ConflictNote) -> "ConflictNoteOut":
        return cls(
            note_text=n.note_text,
            primary_citation=CitationOut.from_citation(n.primary_citation),
            secondary_citation=(
                CitationOut.from_citation(n.secondary_citation)
                if n.secondary_citation is not None
                else None
            ),
        )


class OfficeResolutionOut(BaseModel):
    offices: list[OfficeOut]
    conflict_note: ConflictNoteOut | None
    # Set whenever a district narrowed the regional office list — the
    # Phase 2 district-to-office mapping is an unverified geographic
    # placeholder (see app.engine.offices), never asserted as "nearest."
    district_mapping_caveat: str | None = None

    @classmethod
    def from_resolved(cls, r: engine_types.OfficeResolution) -> "OfficeResolutionOut":
        return cls(
            offices=[OfficeOut.from_resolved(o) for o in r.offices],
            conflict_note=(
                ConflictNoteOut.from_resolved(r.conflict_note)
                if r.conflict_note is not None
                else None
            ),
            district_mapping_caveat=r.district_mapping_caveat,
        )


class AmendmentAlternativeOut(BaseModel):
    fee: FeeOut
    requirements: list[RequirementOut]

    @classmethod
    def from_resolved(
        cls, a: engine_types.AmendmentAlternative
    ) -> "AmendmentAlternativeOut":
        return cls(
            fee=FeeOut.from_resolved(a.fee),
            requirements=[RequirementOut.from_resolved(r) for r in a.requirements],
        )


class ScopeGateOut(BaseModel):
    reason: str


class CaseResolutionOut(BaseModel):
    requirements: list[RequirementOut] = []
    fee: FeeOut | None = None
    offices: OfficeResolutionOut | None = None
    amendment_alternative: AmendmentAlternativeOut | None = None
    scope_gate: ScopeGateOut | None = None

    @classmethod
    def from_resolution_dict(cls, d: dict) -> "CaseResolutionOut":
        """`app.graph.build.run_resolve_action`'s counterpart to
        `from_resolution` — the graph's `resolve` node already
        serializes `CaseResolution` to the same plain-dict shape these
        fields expect (see `app.graph.nodes._resolution_dict`), so
        Pydantic's own nested-dict validation (str -> UUID/datetime
        coercion included) builds the response directly, no
        `engine_types.CaseResolution` object needed."""
        if d.get("scope_gate") is not None:
            return cls(scope_gate=ScopeGateOut(reason=d["scope_gate"]))
        return cls.model_validate(d)

    @classmethod
    def from_resolution(cls, r: engine_types.CaseResolution) -> "CaseResolutionOut":
        if r.scope_gate is not None:
            return cls(scope_gate=ScopeGateOut(reason=r.scope_gate.reason))
        return cls(
            requirements=[RequirementOut.from_resolved(x) for x in r.requirements],
            fee=FeeOut.from_resolved(r.fee) if r.fee is not None else None,
            offices=(
                OfficeResolutionOut.from_resolved(r.offices)
                if r.offices is not None
                else None
            ),
            amendment_alternative=(
                AmendmentAlternativeOut.from_resolved(r.amendment_alternative)
                if r.amendment_alternative is not None
                else None
            ),
        )


class QuestionOut(BaseModel):
    id: uuid.UUID
    prompt: str
    answer_type: str
    # 6.11.2: `prompt`'s rephrased surface wording — equal to `prompt`
    # when rephrasing wasn't attempted, mismatched, or failed. `prompt`
    # itself always stays canonical; this field is presentation-only.
    display_text: str
    # Optional legal/technical reference for a citizen who already knows
    # the terminology — never required to answer `prompt`. Null for
    # every question that has no such reference.
    hint: str | None = None


class RAGAnswerOut(BaseModel):
    text: str
    citations: list[CitationOut]
    grounded: bool

    @classmethod
    def from_response(cls, r: RAGResponse) -> "RAGAnswerOut":
        return cls(
            text=r.text,
            citations=[CitationOut.from_citation(c) for c in r.citations],
            grounded=r.grounded,
        )


class ChatMessageResponse(BaseModel):
    case_id: uuid.UUID
    answer: RAGAnswerOut | None = None
    next_question: QuestionOut | None = None
    # 6.11.3: acknowledgement of exactly the facts recorded this turn —
    # None when nothing was recorded, or acknowledgement generation
    # failed (presentation only; never blocks the turn).
    acknowledgement: str | None = None


class ServiceOut(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    category: str


class ChatMessageOut(BaseModel):
    """6.10: one persisted CHAT_MESSAGE row, as returned by the
    transcript endpoint."""

    id: uuid.UUID
    role: str
    content: str
    created_at: datetime
    intent: str | None = None
    cited_chunk_ids: list[str] | None = None
    # 6.11: the per-turn tool-call trace, when this message was produced
    # by calling one or more tools.
    tool_trace: list[dict] | None = None


class TranscriptOut(BaseModel):
    case_id: uuid.UUID | None
    messages: list[ChatMessageOut]


class StudioOut(BaseModel):
    """Phase 7 (mobile-app-integration): one authorized photo studio, as
    returned by `GET /studios`. Mirrors `engine_types.ResolvedStudio`
    field-for-field, same pattern every other `*Out` model in this file
    uses."""

    id: uuid.UUID
    name: str
    address: str
    phone: str | None
    citation: CitationOut

    @classmethod
    def from_resolved(cls, s: engine_types.ResolvedStudio) -> "StudioOut":
        return cls(
            id=s.id,
            name=s.name,
            address=s.address,
            phone=s.phone,
            citation=CitationOut.from_citation(s.citation),
        )


class StudioResolutionOut(BaseModel):
    district: str
    studios: list[StudioOut]
    receipt_note: str

    @classmethod
    def from_resolved(cls, r: engine_types.StudioResolution) -> "StudioResolutionOut":
        return cls(
            district=r.district,
            studios=[StudioOut.from_resolved(s) for s in r.studios],
            receipt_note=r.receipt_note,
        )


# --- Item 7: user accounts and saved plans -----------------------------


class SignupRequest(BaseModel):
    email: str
    password: str


class SigninRequest(BaseModel):
    email: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class SavePlanRequest(BaseModel):
    case_id: uuid.UUID
    label: str


class SavedPlanOut(BaseModel):
    id: uuid.UUID
    case_id: uuid.UUID
    label: str
    created_at: datetime

    @classmethod
    def from_model(cls, saved_plan) -> "SavedPlanOut":
        return cls(
            id=saved_plan.id,
            case_id=saved_plan.case_id,
            label=saved_plan.label,
            created_at=saved_plan.created_at,
        )
