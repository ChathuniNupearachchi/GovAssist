"""SQLAlchemy models for GovAssist's case-resolution data model.

BACKEND_PLAN.md Phase 2. Its heading says "Thirteen tables in one Alembic
migration" but its own list names 14 (REQUIREMENT_CONDITION, the one
table without its own `id`, is the likely miscount) — confirmed with the
user to build all 14 listed. See the phase-2-data-model change's
proposal.md for the full correction note.

Phase 4 added a 15th table, RESOLUTION_NOTE, plus per-fact
source_document_id columns on Requirement and FeeRule — see the
phase-4-rules-engine change's design.md.

Enum-like columns are plain String with a Postgres CHECK constraint
(added in the migration) rather than a native Postgres ENUM type, so
adding a new allowed value later is one ALTER TABLE instead of an
ALTER TYPE. Every primary key is a client-generated UUID (Python-side
uuid4 default), not a Postgres-side gen_random_uuid(), so it behaves
identically outside Postgres (e.g. in tests) and doesn't depend on a
UUID-generating extension being enabled.
"""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    ARRAY,
    Boolean,
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class Service(Base):
    __tablename__ = "service"

    id: Mapped[uuid.UUID] = _uuid_pk()
    code: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)


class SourceDocument(Base):
    __tablename__ = "source_document"
    __table_args__ = (
        CheckConstraint("document_type IN ('html', 'pdf')", name="ck_source_document_document_type"),
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')", name="ck_source_document_status"
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    source_url: Mapped[str] = mapped_column(String, nullable=False)
    snapshot_path: Mapped[str | None] = mapped_column(String, nullable=True)
    content_hash: Mapped[str] = mapped_column(String, nullable=False)
    document_type: Mapped[str] = mapped_column(String, nullable=False, default="html")
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    # When status was set to "approved" — distinct from RuleVersion.verified_at
    # (a human verifying rule *content*) and from fetched_at (scrape time).
    # This is the "verified as of" date RAG answers cite. See phase-5-rag-layer's
    # design.md.
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class RuleVersion(Base):
    __tablename__ = "rule_version"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'approved', 'superseded')", name="ck_rule_version_status"
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("service.id"), nullable=False
    )
    source_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("source_document.id"), nullable=False
    )
    approved_by: Mapped[str | None] = mapped_column(String, nullable=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="draft")
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    service: Mapped["Service"] = relationship()
    source_document: Mapped["SourceDocument"] = relationship()


class Office(Base):
    __tablename__ = "office"
    __table_args__ = (
        CheckConstraint(
            "type IN ('head', 'regional', 'ds', 'mission')", name="ck_office_type"
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    # One office can serve many districts (five regional offices cover 25
    # districts between them), so this is an array, not a scalar FK — see
    # design.md's "OFFICE.district is ARRAY(String)" decision. Null only
    # for the head office, which is not district-scoped.
    district: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    opening_hours: Mapped[str] = mapped_column(String, nullable=False)


class Requirement(Base):
    __tablename__ = "requirement"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('document', 'step', 'prerequisite')", name="ck_requirement_kind"
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    rule_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rule_version.id"), nullable=False
    )
    office_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("office.id"), nullable=True
    )
    # Per-fact citation, independent of rule_version.source_document_id.
    # Added in Phase 4: a rule version's facts can span more than one
    # source document (e.g. renewal's documents/fees come from id=8, its
    # fingerprints prerequisite from id=7), so each requirement carries
    # its own citation rather than inheriting one. Falls back to the
    # rule version's citation when null (see case-resolution-data-model
    # spec's "Requirements, conditions, and fees resolve per rule
    # version" requirement).
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("source_document.id"), nullable=True
    )
    label: Mapped[str] = mapped_column(String, nullable=False)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    freshness_rule: Mapped[str | None] = mapped_column(String, nullable=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    # Downloadable resources for this requirement (e.g. an application
    # form's PDF and its filling instructions) — a list of
    # {"label": str, "url": str, "type": str} objects, or null when a
    # requirement has none. Reused by every future service's own forms,
    # not special-cased to passports — see case-resolution-data-model
    # spec's "requirement resources" requirement.
    resources: Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True)

    rule_version: Mapped["RuleVersion"] = relationship()
    office: Mapped["Office | None"] = relationship()
    source_document: Mapped["SourceDocument | None"] = relationship()


class Question(Base):
    __tablename__ = "question"
    __table_args__ = (
        CheckConstraint(
            "answer_type IN ('single', 'boolean', 'district')", name="ck_question_answer_type"
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("service.id"), nullable=False
    )
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    answer_type: Mapped[str] = mapped_column(String, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    # Optional legal/technical reference for a citizen who already knows
    # the terminology (e.g. "Section 19(2) of the Citizenship Act,
    # amended by Act No. 18 of 1948") — shown alongside a plain-language
    # `prompt`, never required to answer it. See conversational-intake's
    # "plain language" audit.
    hint: Mapped[str | None] = mapped_column(Text, nullable=True)

    service: Mapped["Service"] = relationship()


class Condition(Base):
    __tablename__ = "condition"
    __table_args__ = (
        CheckConstraint("operator IN ('equals', 'lessThan', 'in')", name="ck_condition_operator"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("question.id"), nullable=False
    )
    attribute: Mapped[str] = mapped_column(String, nullable=False)
    operator: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[str] = mapped_column(String, nullable=False)
    # No self-referential FK anywhere on this model — conditions do not
    # nest, and are not composed with AND/OR (see spec: "A requirement
    # gates on a flat set of independent conditions").

    question: Mapped["Question"] = relationship()


class RequirementCondition(Base):
    __tablename__ = "requirement_condition"

    requirement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("requirement.id"), primary_key=True
    )
    condition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("condition.id"), primary_key=True
    )
    negated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    requirement: Mapped["Requirement"] = relationship()
    condition: Mapped["Condition"] = relationship()


class QuestionCondition(Base):
    """Gates whether a QUESTION is currently relevant — the same flat,
    zero-or-more-conditions-ANDed, each-optionally-negated shape
    REQUIREMENT_CONDITION already uses for requirements, applied to
    intake questions instead. A question with no linked conditions is
    unconditionally relevant (the common case). Reuses `Condition` and
    `app.engine.conditions.condition_link_passes` unchanged — this is
    the same gating mechanism, a different left-hand side.
    """

    __tablename__ = "question_condition"

    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("question.id"), primary_key=True
    )
    condition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("condition.id"), primary_key=True
    )
    negated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    question: Mapped["Question"] = relationship()
    condition: Mapped["Condition"] = relationship()


class FeeRule(Base):
    __tablename__ = "fee_rule"
    __table_args__ = (
        CheckConstraint("basis IN ('normal', 'urgent')", name="ck_fee_rule_basis"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    rule_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rule_version.id"), nullable=False
    )
    condition_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("condition.id"), nullable=True
    )
    # Per-fact citation, independent of rule_version.source_document_id —
    # same rationale as Requirement.source_document_id (Phase 4).
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("source_document.id"), nullable=True
    )
    base_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    penalty_amount: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    basis: Mapped[str] = mapped_column(String, nullable=False, default="normal")

    rule_version: Mapped["RuleVersion"] = relationship()
    condition: Mapped["Condition | None"] = relationship()
    source_document: Mapped["SourceDocument | None"] = relationship()


class Case(Base):
    __tablename__ = "case"

    id: Mapped[uuid.UUID] = _uuid_pk()
    service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("service.id"), nullable=False
    )
    device_ref: Mapped[str] = mapped_column(String, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    outdated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    service: Mapped["Service"] = relationship()


class CaseAnswer(Base):
    __tablename__ = "case_answer"

    id: Mapped[uuid.UUID] = _uuid_pk()
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("case.id"), nullable=False
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("question.id"), nullable=False
    )
    value: Mapped[str] = mapped_column(String, nullable=False)

    case: Mapped["Case"] = relationship()
    question: Mapped["Question"] = relationship()


class PlanItem(Base):
    __tablename__ = "plan_item"

    id: Mapped[uuid.UUID] = _uuid_pk()
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("case.id"), nullable=False
    )
    requirement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("requirement.id"), nullable=False
    )
    rule_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rule_version.id"), nullable=False
    )
    collected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)

    case: Mapped["Case"] = relationship()
    requirement: Mapped["Requirement"] = relationship()
    rule_version: Mapped["RuleVersion"] = relationship()


class DocumentChunk(Base):
    __tablename__ = "document_chunk"
    __table_args__ = (
        Index(
            "ix_document_chunk_search_vector", "search_vector", postgresql_using="gin"
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    source_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("source_document.id"), nullable=False
    )
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(384), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    # Phase 6.6: document_title, section_heading, content_type
    # (prose|table|list), source_url — see document-chunking spec's
    # "Every chunk carries metadata" requirement. Python attribute is
    # `chunk_metadata`, not `metadata` — that name is reserved on every
    # SQLAlchemy declarative class for the schema-level MetaData
    # instance (`Base.metadata`); the DB column itself is still named
    # `metadata`, per the spec.
    chunk_metadata: Mapped[dict | None] = mapped_column(
        "metadata", JSONB, nullable=True
    )
    # Phase 6.7: Postgres-native full-text search alongside pgvector
    # cosine similarity — a STORED generated column (computed by
    # Postgres on every insert/update, not maintained in application
    # code), GIN-indexed for `plainto_tsquery` matching. See
    # case-resolution-data-model spec's "chunk's text also supports
    # full-text search" requirement.
    search_vector: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('english', chunk_text)", persisted=True),
        nullable=True,
    )

    source_document: Mapped["SourceDocument"] = relationship()


class AuthorizedStudio(Base):
    """Phase 9: authorized photo studios, by district — a relational
    lookup, not a RAG document. See the phase-9-service-expansion
    migration's docstring for why."""

    __tablename__ = "authorized_studio"

    id: Mapped[uuid.UUID] = _uuid_pk()
    # Canonical spelling (app.chat.deterministic.DISTRICTS), not the
    # source site's own spelling or numeric id.
    district: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    address: Mapped[str] = mapped_column(String, nullable=False)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    source_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("source_document.id"), nullable=False
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    source_document: Mapped["SourceDocument"] = relationship()


class AdminUser(Base):
    __tablename__ = "admin_user"
    __table_args__ = (
        CheckConstraint("role IN ('reviewer', 'approver')", name="ck_admin_user_role"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    role: Mapped[str] = mapped_column(String, nullable=False)


class ChatMessage(Base):
    """Phase 6.10: the durable, per-case conversation record — what a
    citizen was actually told survives a closed app, even though the
    engine already remembered every fact through CASE_ANSWER. Also the
    audit trail: what a citizen actually asked, and what the system
    actually answered."""

    __tablename__ = "chat_message"
    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant')", name="ck_chat_message_role"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("case.id"), nullable=False
    )
    role: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    # "answer" | "situation" | "question" | null (deterministic match, or
    # not classified — e.g. the assistant's own messages).
    intent: Mapped[str | None] = mapped_column(String, nullable=True)
    # Chunk ids the assistant's answer actually cited (6.9's verified
    # set) — null for a user message, which cites nothing.
    cited_chunk_ids: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    # Phase 6.11: the per-turn tool-call trace (name, arguments, order,
    # result for every tool call made while producing this message) —
    # null for a user message or an assistant message answered without
    # calling any tool. Same shape/precedent as `cited_chunk_ids`.
    tool_trace: Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True)

    case: Mapped["Case"] = relationship()


class ResolutionNote(Base):
    """An advisory note attached to case resolution — not a document, step,
    or prerequisite a citizen collects, but a fact that changes what the
    citizen should do before acting on a resolution (Phase 4: the
    urgent-service office conflict). Citizen-facing, so it lives in data
    per CLAUDE.md's "rules live in data, not code" rather than as a
    resolver-code constant — see phase-4-rules-engine's design.md.
    """

    __tablename__ = "resolution_note"

    id: Mapped[uuid.UUID] = _uuid_pk()
    code: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    note_text: Mapped[str] = mapped_column(Text, nullable=False)
    primary_source_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("source_document.id"), nullable=False
    )
    secondary_source_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("source_document.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    primary_source_document: Mapped["SourceDocument"] = relationship(
        foreign_keys=[primary_source_document_id]
    )
    secondary_source_document: Mapped["SourceDocument | None"] = relationship(
        foreign_keys=[secondary_source_document_id]
    )