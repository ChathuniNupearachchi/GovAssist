"""Phase 9: authorized photo studio resolver.

Exact-match district lookup against `AUTHORIZED_STUDIO` — the same
shape as `app.engine.offices.resolve_offices`'s district filter, not a
RAG retrieval (see phase-9-service-expansion's design.md's "Photo
studios are data, not a document" decision). `district` is expected in
this project's own canonical spelling (`app.chat.deterministic.
DISTRICTS`) — the same value the existing `district` intake question
already produces, so this reuses that question rather than needing a
second, studio-specific district question with different wording.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.engine.types import Citation, ResolvedStudio, StudioResolution
from app.models import AuthorizedStudio

# Sourced directly from id=7 (already ingested): "The studio will issue
# you a acknowledgement note which should be submitted along with your
# application" — stated once here, not duplicated per studio, since it
# applies regardless of which authorized studio the citizen visits.
RECEIPT_NOTE = (
    "The studio will give you an acknowledgement note (not a printed "
    "photo) — submit it with your application. Only photos taken "
    "within the last 6 months are valid."
)


def resolve_studios(db: Session, district: str) -> StudioResolution:
    rows = db.scalars(
        select(AuthorizedStudio)
        .where(AuthorizedStudio.district == district)
        .order_by(AuthorizedStudio.name)
    ).all()

    studios = [
        ResolvedStudio(
            id=row.id,
            name=row.name,
            address=row.address,
            phone=row.phone,
            citation=Citation(
                source_document_id=row.source_document_id,
                source_url=row.source_document.source_url,
                verified_at=row.verified_at,
            ),
        )
        for row in rows
    ]
    return StudioResolution(district=district, studios=studios, receipt_note=RECEIPT_NOTE)
