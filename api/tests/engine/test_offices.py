"""11.2 Office resolver unit tests — determinism, conflict note, no DS."""

from app.engine.offices import resolve_offices


def test_repeated_calls_return_identical_results(db):
    first = resolve_offices(db, district="Kandy", basis="urgent")
    second = resolve_offices(db, district="Kandy", basis="urgent")

    assert [o.id for o in first.offices] == [o.id for o in second.offices]
    assert (first.conflict_note is not None) == (second.conflict_note is not None)


def test_urgent_includes_conflict_note(db):
    result = resolve_offices(db, district="Kandy", basis="urgent")
    assert result.conflict_note is not None
    assert "one-day" in result.conflict_note.note_text or "One day" in result.conflict_note.note_text


def test_normal_has_no_conflict_note(db):
    result = resolve_offices(db, district="Kandy", basis="normal")
    assert result.conflict_note is None


def test_no_divisional_secretariat_ever_returned(db):
    for district in ("Kandy", "Colombo", None):
        result = resolve_offices(db, district=district, basis="urgent")
        assert all(o.type != "ds" for o in result.offices)


def test_district_narrows_regional_offices(db):
    result = resolve_offices(db, district="Kandy", basis="normal")
    regional_names = [o.name for o in result.offices if o.type == "regional"]
    assert regional_names == ["Kandy Regional Office"]
    # Head Office and Missions remain regardless of district
    assert any(o.type == "head" for o in result.offices)
    assert any(o.type == "mission" for o in result.offices)


def test_no_district_lists_all_regional_offices(db):
    result = resolve_offices(db, district=None, basis="normal")
    regional_names = {o.name for o in result.offices if o.type == "regional"}
    assert len(regional_names) == 5
