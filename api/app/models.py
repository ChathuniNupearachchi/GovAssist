"""SQLAlchemy models for GovAssist's case-resolution data model.

BACKEND_PLAN.md Phase 2. Its heading says "Thirteen tables in one Alembic
migration" but its own list names 14 (REQUIREMENT_CONDITION, the one
table without its own `id`, is the likely miscount) — confirmed with the
user to build all 14 listed. See the phase-2-data-model change's
proposal.md for the full correction note.

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
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
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
    label: Mapped[str] = mapped_column(String, nullable=False)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    freshness_rule: Mapped[str | None] = mapped_column(String, nullable=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)

    rule_version: Mapped["RuleVersion"] = relationship()
    office: Mapped["Office | None"] = relationship()


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
    base_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    penalty_amount: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    basis: Mapped[str] = mapped_column(String, nullable=False, default="normal")

    rule_version: Mapped["RuleVersion"] = relationship()
    condition: Mapped["Condition | None"] = relationship()


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

    id: Mapped[uuid.UUID] = _uuid_pk()
    source_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("source_document.id"), nullable=False
    )
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(384), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)

    source_document: Mapped["SourceDocument"] = relationship()


class AdminUser(Base):
    __tablename__ = "admin_user"
    __table_args__ = (
        CheckConstraint("role IN ('reviewer', 'approver')", name="ck_admin_user_role"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    role: Mapped[str] = mapped_column(String, nullable=False)