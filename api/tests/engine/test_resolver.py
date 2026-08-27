"""14.3 Unit tests for the scope gate and the amendment branch."""

import pytest

from app.engine.resolver import resolve_case

BASE_ANSWERS = {
    "age": "30",
    "applying_from": "sri_lanka",
    "holds_passport": "false",
    "name_changed": "false",
    "dual_citizen": "false",
    "section_19_2": "false",
    "profession": "",
    "buddhist_priest": "false",
    "district": "Colombo",
    "photo_district": "Colombo",
    "service_basis": "normal",
}


def test_under_16_returns_scope_gate_no_plan(db):
    result = resolve_case(db, {**BASE_ANSWERS, "age": "10"})
    assert result.scope_gate is not None
    assert result.requirements == []
    assert result.fee is None
    assert result.offices is None


def test_adult_does_not_trigger_scope_gate(db):
    result = resolve_case(db, BASE_ANSWERS)
    assert result.scope_gate is None
    assert result.requirements
    assert result.fee is not None


def test_name_change_surfaces_amendment_alternative(db):
    result = resolve_case(db, {**BASE_ANSWERS, "name_changed": "true"})
    assert result.amendment_alternative is not None
    assert result.amendment_alternative.fee.base_amount == 1200.00
    # Phase 9's amendment implementation (all 6 alteration types) added
    # the application form as its own Requirement — the alternative
    # specifically resolves the Change of Name alteration type (see
    # `app.engine.resolver._amendment_alternative`), so it now includes
    # the form alongside the two Change-of-Name documents, not just the
    # two documents the old 2-Requirement stub had.
    assert {r.label for r in result.amendment_alternative.requirements} == {
        "Completed Alteration Application Form",
        "Passport",
        "Marriage certificate (to confirm name change)",
    }
    # The renewal resolution is still present alongside the alternative
    assert result.requirements
    assert result.fee is not None


def test_no_name_change_has_no_amendment_alternative(db):
    result = resolve_case(db, BASE_ANSWERS)
    assert result.amendment_alternative is None


def test_missing_age_raises(db):
    with pytest.raises(ValueError):
        resolve_case(db, {k: v for k, v in BASE_ANSWERS.items() if k != "age"})
