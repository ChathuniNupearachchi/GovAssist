"""Golden test set for `passport-amendment` — mirrors
`test_new_applicant_golden.py`'s structure. All amendment cases use a
flat LKR 1,200 fee, so that's checked once separately rather than
repeated in every scenario dict."""

import pytest

from app.engine.resolver import AMENDMENT_SERVICE_CODE, resolve_case
from tests.engine.amendment_golden_scenarios import AMENDMENT_GOLDEN_SCENARIOS


@pytest.mark.parametrize(
    "scenario", AMENDMENT_GOLDEN_SCENARIOS, ids=[s["name"] for s in AMENDMENT_GOLDEN_SCENARIOS]
)
def test_amendment_golden_scenario(db, scenario):
    result = resolve_case(db, scenario["answers"], service_code=AMENDMENT_SERVICE_CODE)

    assert result.scope_gate is None

    actual_labels = {r.label for r in result.requirements}
    assert actual_labels == scenario["expected_labels"], scenario["name"]

    assert result.fee.base_amount == 1200.00, scenario["name"]

    actual_offices = {o.name for o in result.offices.offices}
    assert actual_offices == scenario["expected_offices"], scenario["name"]


def test_every_alteration_type_has_the_application_form(db):
    from tests.engine.amendment_golden_scenarios import APPLICATION_FORM_LABEL

    for scenario in AMENDMENT_GOLDEN_SCENARIOS:
        result = resolve_case(db, scenario["answers"], service_code=AMENDMENT_SERVICE_CODE)
        labels = {r.label for r in result.requirements}
        assert APPLICATION_FORM_LABEL in labels, f"{scenario['name']}: no application form requirement"


def test_child_name_deletion_is_not_an_alteration_type(db):
    """design.md's Round 2 correction: child-name-deletion is its own
    service, not an amendment alteration type, even though id=10's own
    table lists it alongside the others. No Condition should exist for
    an alteration_type value naming it."""
    from sqlalchemy import select

    from app.engine.resolver import _approved_rule_version
    from app.models import Condition

    rule_version = _approved_rule_version(db, AMENDMENT_SERVICE_CODE)
    conditions = db.scalars(
        select(Condition).where(Condition.attribute == "alteration_type")
    ).all()
    values = {c.value for c in conditions}
    assert "child_name_deletion" not in values
    assert "deletion_of_a_childs_name" not in values


def test_every_requirement_and_fee_has_a_citation(db):
    for scenario in AMENDMENT_GOLDEN_SCENARIOS:
        result = resolve_case(db, scenario["answers"], service_code=AMENDMENT_SERVICE_CODE)
        for r in result.requirements:
            assert r.citation.source_document_id and r.citation.source_url, (
                f"{scenario['name']}: {r.label!r} has no citation"
            )
        assert result.fee.citation.source_document_id, f"{scenario['name']}: fee has no citation"
