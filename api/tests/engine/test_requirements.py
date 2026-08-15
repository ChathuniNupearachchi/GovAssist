"""9.2 Requirement resolver unit tests + 12.2 prerequisite ordering."""

from app.engine.requirements import resolve_requirements
from app.models import RuleVersion, Service


def _renewal_rule_version_id(db):
    service = db.query(Service).filter(Service.code == "passport-renewal").first()
    return (
        db.query(RuleVersion)
        .filter(RuleVersion.service_id == service.id, RuleVersion.status == "approved")
        .first()
        .id
    )


BASE_ANSWERS = {
    "age": "30",
    "holds_passport": "false",
    "name_changed": "false",
    "dual_citizen": "false",
    "section_19_2": "false",
    "profession": "",
    "buddhist_priest": "false",
    "district": "Colombo",
    "service_basis": "normal",
}


def test_name_change_changes_the_returned_set(db):
    rv_id = _renewal_rule_version_id(db)

    without_change = resolve_requirements(db, rv_id, BASE_ANSWERS)
    with_change = resolve_requirements(
        db, rv_id, {**BASE_ANSWERS, "name_changed": "true"}
    )

    without_labels = {r.label for r in without_change}
    with_labels = {r.label for r in with_change}

    assert without_labels != with_labels
    assert not any("Marriage certificate" in label for label in without_labels)
    assert any("Marriage certificate" in label for label in with_labels)


def test_dual_citizen_excludes_standard_set(db):
    rv_id = _renewal_rule_version_id(db)
    resolved = resolve_requirements(
        db, rv_id, {**BASE_ANSWERS, "dual_citizen": "true"}
    )
    labels = {r.label for r in resolved}

    assert any("Dual Citizenship Certificate" in label for label in labels)
    assert not any(
        label.startswith("Original Birth Certificate") for label in labels
    )
    assert not any(
        label.startswith("Original National Identity Card") for label in labels
    )
    # The dual-citizen birth certificate / NIC items are present instead
    assert any(label == "Birth Certificate with a photocopy." for label in labels)
    assert any(label == "National Identity Card with a photocopy." for label in labels)


def test_section_19_2_includes_new_nic_prerequisite(db):
    rv_id = _renewal_rule_version_id(db)
    resolved = resolve_requirements(
        db,
        rv_id,
        {**BASE_ANSWERS, "dual_citizen": "true", "section_19_2": "true"},
    )
    labels = {r.label for r in resolved}
    assert any("new National Identity Card" in label for label in labels)


def test_section_19_2_absent_without_dual_citizen(db):
    rv_id = _renewal_rule_version_id(db)
    resolved = resolve_requirements(db, rv_id, BASE_ANSWERS)
    labels = {r.label for r in resolved}
    assert not any("new National Identity Card" in label for label in labels)


def test_studio_acknowledgement_is_first(db):
    rv_id = _renewal_rule_version_id(db)
    resolved = resolve_requirements(db, rv_id, BASE_ANSWERS)
    assert resolved[0].label == "Photo studio acknowledgement"


def test_fingerprints_prerequisite_gated_by_age(db):
    rv_id = _renewal_rule_version_id(db)
    adult = resolve_requirements(db, rv_id, {**BASE_ANSWERS, "age": "30"})
    over_60 = resolve_requirements(db, rv_id, {**BASE_ANSWERS, "age": "65"})

    assert any("fingerprints" in r.label.lower() for r in adult)
    assert not any("fingerprints" in r.label.lower() for r in over_60)


def test_every_requirement_carries_a_citation(db):
    rv_id = _renewal_rule_version_id(db)
    resolved = resolve_requirements(db, rv_id, BASE_ANSWERS)
    assert resolved  # sanity: at least the studio acknowledgement
    for r in resolved:
        assert r.citation.source_document_id is not None
        assert r.citation.verified_at is not None
