"""phase 6.13 remove colombo from kurunegala office district mapping

Revision ID: b961caad3760
Revises: b8879c5949b2
Create Date: 2026-08-25 22:47:57.481661

Bug fix (manual-QA bug #1, "office resolver — most serious"): a
Colombo-district applicant was returned Kurunegala Regional Office
(~94km away) as their assigned regional office, because the Phase 2
seed migration's district-to-office mapping — itself recorded there as
an unverified geographic placeholder, not sourced from any published
Department jurisdiction list — put Colombo in Kurunegala Regional
Office's district array alongside Gampaha, Kalutara, Kegalle,
Ratnapura, Ampara, Batticaloa, and Trincomalee (a ten-district
catch-all spanning both coasts).

This migration does NOT attempt to fix that mapping wholesale, and does
NOT reassign Colombo to a different regional office — either would be
exactly the "assert an office is nearest" guess the bug-fix instruction
explicitly forbids, since the Department's actual jurisdiction
boundaries remain unpublished and unverified. It removes only the one
specific, independently justifiable case: Head Office itself is
physically located in Colombo district (Battaramulla) and is already
unconditionally included in every office resolution regardless of
district (see app/engine/offices.py) — so a Colombo applicant already
has an in-district option without needing a regional office assignment
at all. The other 24 districts' mappings are untouched here and remain
flagged as unverified via OfficeResolution.district_mapping_caveat.

Idempotent: array_remove is a no-op if 'Colombo' is already absent, so
this is safe to run more than once.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b961caad3760'
down_revision: Union[str, Sequence[str], None] = 'b8879c5949b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_KURUNEGALA_OFFICE_ID = "00000000-0000-0000-0000-000000000005"


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE office SET district = array_remove(district, 'Colombo') "
            "WHERE id = :office_id"
        ).bindparams(office_id=_KURUNEGALA_OFFICE_ID)
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE office SET district = array_append(district, 'Colombo') "
            "WHERE id = :office_id"
        ).bindparams(office_id=_KURUNEGALA_OFFICE_ID)
    )
