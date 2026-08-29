"""admin dashboard tables and read-only role

Revision ID: d3f1a9c02b7e
Revises: ad2462b13c70
Create Date: 2026-08-28 00:00:00.000000

admin-dashboard change, tasks 1.1-1.3. Adds the four admin-owned tables
(ADMIN_ACTION, ADMIN_DRAFT, ADMIN_OVERLAY, plus password_hash on the
existing-but-until-now-unused ADMIN_USER) and provisions a dedicated
Postgres role, `govassist_admin_readonly`, granted SELECT only on every
table the citizen-facing system reads and full CRUD only on the four
admin-owned tables — enforced at the database level per design.md's
"Database-level read-only enforcement via a dedicated Postgres role"
decision, not by application-code convention.

The role's password is read from the `ADMIN_READONLY_ROLE_PASSWORD`
environment variable at migration time (never hardcoded), matching this
project's existing convention of keeping every secret out of version
control (api/.env, gitignored). Skipped when unset only for environments
where a superuser DATABASE_URL isn't available to run CREATE ROLE (e.g.
some managed-Postgres CI setups) — in that case the tables are still
created, and someone with sufficient Postgres privileges must run the
role/grant statements manually before /admin/api can connect with the
intended read-only role. See design.md's Migration Plan.
"""
from typing import Sequence, Union
import os

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'd3f1a9c02b7e'
down_revision: Union[str, Sequence[str], None] = 'ad2462b13c70'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ADMIN_READONLY_ROLE = "govassist_admin_readonly"

# Every table the citizen-facing system reads (proposal.md's list) —
# SELECT only.
_LIVE_TABLES = [
    "service", "rule_version", "requirement", "condition",
    "requirement_condition", "fee_rule", "question", "office",
    "source_document", "document_chunk", "case", "case_answer",
    "plan_item", "authorized_studio", "chat_message",
]

# The dashboard's own tables — full CRUD.
_ADMIN_OWNED_TABLES = ["admin_user", "admin_action", "admin_draft", "admin_overlay"]


def upgrade() -> None:
    op.add_column("admin_user", sa.Column("password_hash", sa.String(), nullable=True))
    # Nullable on add so this migration never fails against existing rows;
    # the app enforces "never plaintext, always hashed at signup" going
    # forward (see admin-auth spec's "Admin signup" requirement) rather
    # than a NOT NULL constraint that would need a backfill for a table
    # that has had zero real rows to date.

    op.create_table(
        "admin_action",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("admin_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("target_type", sa.String(), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("action IN ('approve', 'reject')", name="ck_admin_action_action"),
        sa.ForeignKeyConstraint(["admin_id"], ["admin_user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "admin_draft",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("service_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("based_on_rule_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')", name="ck_admin_draft_status"
        ),
        sa.ForeignKeyConstraint(["service_id"], ["service.id"]),
        sa.ForeignKeyConstraint(["based_on_rule_version_id"], ["rule_version.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "admin_overlay",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_type", sa.String(), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("operation", sa.String(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "target_type IN ('service', 'source_document')", name="ck_admin_overlay_target_type"
        ),
        sa.CheckConstraint(
            "operation IN ('create', 'update', 'delete')", name="ck_admin_overlay_operation"
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    _create_readonly_role_and_grants()


def downgrade() -> None:
    if _role_exists():
        op.execute(
            sa.text(
                f"REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM {_ADMIN_READONLY_ROLE}"
            )
        )
    op.execute(sa.text(f"DROP ROLE IF EXISTS {_ADMIN_READONLY_ROLE}"))

    op.drop_table("admin_overlay")
    op.drop_table("admin_draft")
    op.drop_table("admin_action")
    op.drop_column("admin_user", "password_hash")


def _role_exists() -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text("SELECT 1 FROM pg_roles WHERE rolname = :role"),
        {"role": _ADMIN_READONLY_ROLE},
    )
    return result.first() is not None


def _create_readonly_role_and_grants() -> None:
    password = os.environ.get("ADMIN_READONLY_ROLE_PASSWORD")
    if not password:
        # See module docstring: tables still get created; the role must
        # be provisioned manually in environments with no superuser
        # connection available to this migration.
        return

    if not _role_exists():
        # CREATE ROLE's PASSWORD clause takes a string literal, not a bind
        # parameter — Postgres's DDL grammar doesn't accept one there.
        # `password` comes from a deployer-controlled env var, never
        # request input, so literal-escaping (doubling embedded quotes)
        # is sufficient here.
        escaped_password = password.replace("'", "''")
        op.execute(
            sa.text(f"CREATE ROLE {_ADMIN_READONLY_ROLE} LOGIN PASSWORD '{escaped_password}'")
        )

    # Double-quoted: "case" is a reserved word in Postgres and would
    # otherwise be a syntax error in this unquoted table list.
    live_tables = ", ".join(f'"{t}"' for t in _LIVE_TABLES)
    op.execute(sa.text(f"GRANT SELECT ON {live_tables} TO {_ADMIN_READONLY_ROLE}"))

    admin_tables = ", ".join(f'"{t}"' for t in _ADMIN_OWNED_TABLES)
    op.execute(
        sa.text(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {admin_tables} TO {_ADMIN_READONLY_ROLE}")
    )
