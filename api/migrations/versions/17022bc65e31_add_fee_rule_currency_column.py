"""add fee_rule currency column

Revision ID: 17022bc65e31
Revises: 8a04052dab33
Create Date: 2026-08-28 04:25:04.750706

Only the fee_rule.currency column (seven-corrections round, item 5) is
this migration's actual intent — autogenerate also picked up the
LangGraph checkpointer tables (managed by langgraph's own Postgres
checkpointer setup, not app/models.py) and an authorized_studio index
that isn't declared in models.py either; both trimmed out here as
unrelated drift, not part of this change.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '17022bc65e31'
down_revision: Union[str, Sequence[str], None] = '8a04052dab33'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('fee_rule', sa.Column('currency', sa.String(), server_default='LKR', nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('fee_rule', 'currency')
