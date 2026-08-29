"""phase 9 authorized studio table

Revision ID: 8a04052dab33
Revises: b961caad3760
Create Date: 2026-08-27 00:00:00.000000

Phase 9 (service expansion): authorized photo studios, by district — a
relational lookup, not a RAG document (~1,000 rows across 25 districts
is structured reference data with an exact-match access pattern, the
same shape as OFFICE.district — see phase-9-service-expansion's
design.md's "Photo studios are data, not a document" decision).

`district` is normalized to this project's own canonical spelling at
scrape time (app.ingestion.sources.STUDIO_DISTRICT_IDS), never the
source site's own spelling or numeric id, so lookups are a plain
equality filter exactly like OFFICE.district membership checks.
`source_document_id` traces every row to the SOURCE_DOCUMENT row
representing the json/function.php data endpoint itself (not a
human-readable page) — every requirement still carries its source and a
verified-as-of date per CLAUDE.md, even though the source is a data
endpoint rather than a page.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '8a04052dab33'
down_revision: Union[str, Sequence[str], None] = 'b961caad3760'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "authorized_studio",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("district", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("address", sa.String(), nullable=False),
        sa.Column("phone", sa.String(), nullable=True),
        sa.Column(
            "source_document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("source_document.id"),
            nullable=False,
        ),
        sa.Column("verified_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_authorized_studio_district", "authorized_studio", ["district"]
    )


def downgrade() -> None:
    op.drop_index("ix_authorized_studio_district", table_name="authorized_studio")
    op.drop_table("authorized_studio")
