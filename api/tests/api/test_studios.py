"""Phase 7 (mobile-app-integration): route-level tests for
`GET /studios`. All 25 canonical districts already carry real
live-scraped `AuthorizedStudio` rows (Phase 9's studio scraper, 1,420
total) — these tests are written to coexist with that data rather than
assume any district starts empty, and restore anything they delete.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import AuthorizedStudio, SourceDocument

_TEST_DISTRICT = "Kilinochchi"
_EMPTY_TEST_DISTRICT = "Mannar"


def _seed_studio(db, district: str, name: str) -> AuthorizedStudio:
    doc = db.scalars(select(SourceDocument)).first()
    assert doc is not None, "expected at least one SourceDocument already seeded"
    studio = AuthorizedStudio(
        district=district,
        name=name,
        address="123 Test Road",
        phone="011-2345678",
        source_document_id=doc.id,
        verified_at=datetime.now(timezone.utc),
    )
    db.add(studio)
    db.commit()
    db.refresh(studio)
    return studio


def _delete_studios(db, ids: list) -> None:
    db.query(AuthorizedStudio).filter(AuthorizedStudio.id.in_(ids)).delete(
        synchronize_session=False
    )
    db.commit()


def test_district_with_studios_returns_them_ordered_by_name(client):
    """Doesn't assume the district starts empty — asserts the two
    inserted studios are both present and ordered correctly relative
    to each other, not that they're the only two returned."""
    db = SessionLocal()
    try:
        b = _seed_studio(db, _TEST_DISTRICT, "Zzz Test Studio Beta")
        a = _seed_studio(db, _TEST_DISTRICT, "Zzz Test Studio Alpha")
        try:
            r = client.get("/studios", params={"district": _TEST_DISTRICT})
            assert r.status_code == 200
            body = r.json()
            assert body["district"] == _TEST_DISTRICT
            names = [s["name"] for s in body["studios"]]
            assert "Zzz Test Studio Alpha" in names
            assert "Zzz Test Studio Beta" in names
            assert names.index("Zzz Test Studio Alpha") < names.index("Zzz Test Studio Beta")
        finally:
            _delete_studios(db, [a.id, b.id])
    finally:
        db.close()


def test_district_with_no_studios_returns_empty_list_not_error(client):
    """Every canonical district already has real seeded studios, so
    this temporarily removes `_EMPTY_TEST_DISTRICT`'s rows to exercise
    the empty-result path, then restores exactly what it removed."""
    db = SessionLocal()
    try:
        existing = db.scalars(
            select(AuthorizedStudio).where(AuthorizedStudio.district == _EMPTY_TEST_DISTRICT)
        ).all()
        removed = [
            {
                "district": s.district,
                "name": s.name,
                "address": s.address,
                "phone": s.phone,
                "source_document_id": s.source_document_id,
                "verified_at": s.verified_at,
            }
            for s in existing
        ]
        db.query(AuthorizedStudio).filter(
            AuthorizedStudio.district == _EMPTY_TEST_DISTRICT
        ).delete(synchronize_session=False)
        db.commit()
        try:
            r = client.get("/studios", params={"district": _EMPTY_TEST_DISTRICT})
            assert r.status_code == 200
            body = r.json()
            assert body["studios"] == []
            # The receipt note is always present, even for an empty result.
            assert body["receipt_note"]
        finally:
            for row in removed:
                db.add(AuthorizedStudio(**row))
            db.commit()
    finally:
        db.close()


def test_missing_district_returns_422(client):
    r = client.get("/studios")
    assert r.status_code == 422


def test_unrecognized_district_returns_422(client):
    r = client.get("/studios", params={"district": "Not A Real District"})
    assert r.status_code == 422


def test_every_studio_carries_a_citation(client):
    db = SessionLocal()
    try:
        studio = _seed_studio(db, _TEST_DISTRICT, "Zzz Citation Test Studio")
        try:
            r = client.get("/studios", params={"district": _TEST_DISTRICT})
            assert r.status_code == 200
            returned = next(
                s for s in r.json()["studios"] if s["name"] == "Zzz Citation Test Studio"
            )
            citation = returned["citation"]
            assert citation["source_document_id"]
            assert citation["source_url"]
        finally:
            _delete_studios(db, [studio.id])
    finally:
        db.close()
