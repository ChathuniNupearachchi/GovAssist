"""Phase 9: authorized-photo-studio scraper.

Fetches the `json/function.php` data endpoint once per district (25
requests, same rate-limited/User-Agent-identified politeness every
other fetch in this project uses — see `app.scraper.fetch`), parses the
returned `<tr>` rows, and persists them as `AuthorizedStudio` rows keyed
by this project's own canonical district spelling — never the source
site's numeric id or its own spelling variants (`Kaluthara`, `Mathale`,
etc.) — see `app.ingestion.sources.STUDIO_DISTRICT_IDS` for the mapping,
verified directly against the site's own `<option>` markup, not
guessed.

Each district's response is snapshotted and recorded as its own
`SourceDocument` row (`document_type="html"` — the endpoint returns an
HTML fragment, not JSON, confirmed directly) so every studio row still
traces to a dated, content-addressed source per CLAUDE.md's "every
requirement carries its source" rule, even though the source is a data
endpoint rather than a human-readable page.

Run with:  python -m app.ingestion.studio_scraper
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.ingestion.sources import STUDIO_DISTRICT_IDS
from app.models import AuthorizedStudio, SourceDocument
from app.scraper.fetch import fetch_and_snapshot_post

STUDIO_ENDPOINT_URL = "https://www.immigration.gov.lk/json/function.php"

_ROW_RE = re.compile(
    r"<tr>\s*<td>(?P<num>\d*)</td>\s*<td>(?P<name>.*?)</td>\s*"
    r"<td>(?P<address>.*?)</td>\s*<td>(?P<phone>.*?)</td>\s*</tr>",
    re.IGNORECASE | re.DOTALL,
)


def _parse_rows(html_fragment: str) -> list[tuple[str, str, str]]:
    """Returns [(name, address, phone), ...] — phone may be an empty
    string (a handful of source rows have no phone at all; recorded as
    empty, not fabricated)."""
    rows = []
    for match in _ROW_RE.finditer(html_fragment):
        name = match.group("name").strip()
        address = match.group("address").strip()
        phone = match.group("phone").strip()
        if name:
            rows.append((name, address, phone))
    return rows


def scrape_district(db: Session, district_id: str, district_name: str) -> list[AuthorizedStudio]:
    """Fetches, snapshots, and persists one district's studio list.
    Idempotent per district: existing AuthorizedStudio rows for this
    district are replaced, not accumulated — a re-run reflects the
    source's current list, not a merge with a stale one."""
    body = f"action_type=view&seldisid={district_id}"
    content_hash, snapshot_path = fetch_and_snapshot_post(STUDIO_ENDPOINT_URL, body, extension=".html")

    # A synthetic, distinguishing source_url for citation display — the
    # endpoint itself has no natural per-district URL (it's a POST body
    # param), so this is what a citation/audit trail shows.
    source_url = f"{STUDIO_ENDPOINT_URL}?action_type=view&seldisid={district_id}"

    document = db.scalars(
        select(SourceDocument).where(SourceDocument.content_hash == content_hash)
    ).first()
    if document is None:
        document = SourceDocument(
            source_url=source_url,
            snapshot_path=snapshot_path,
            content_hash=content_hash,
            document_type="html",
            fetched_at=datetime.now(timezone.utc),
            status="pending",
        )
        db.add(document)
        db.flush()

    from app.scraper.fetch import resolve_snapshot_path

    html_fragment = resolve_snapshot_path(snapshot_path).read_text(encoding="utf-8")
    parsed_rows = _parse_rows(html_fragment)

    db.query(AuthorizedStudio).filter(AuthorizedStudio.district == district_name).delete()

    studios = []
    for name, address, phone in parsed_rows:
        studio = AuthorizedStudio(
            district=district_name,
            name=name,
            address=address,
            phone=phone or None,
            source_document_id=document.id,
            verified_at=datetime.now(timezone.utc),
        )
        db.add(studio)
        studios.append(studio)

    # Approve immediately — same scripted-approval justification Phase
    # 5's phase5_approve_documents used (this content was verified
    # directly against the live endpoint), and required for consistency:
    # AuthorizedStudio rows are retrieved via a direct district-equality
    # query (app.engine.offices-style), not RAG's approved-only scoping,
    # but the underlying SourceDocument should still reflect a verified,
    # not merely fetched, state.
    document.status = "approved"
    document.approved_at = datetime.now(timezone.utc)

    db.commit()
    return studios


def scrape_all_districts(db: Session) -> dict[str, int]:
    counts: dict[str, int] = {}
    for district_id, district_name in STUDIO_DISTRICT_IDS.items():
        studios = scrape_district(db, district_id, district_name)
        counts[district_name] = len(studios)
    return counts


def main() -> None:
    db = SessionLocal()
    try:
        counts = scrape_all_districts(db)
        total = sum(counts.values())
        print(f"Scraped {total} authorized studios across {len(counts)} districts:")
        for district, count in counts.items():
            print(f"  {count:>4}  {district}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
