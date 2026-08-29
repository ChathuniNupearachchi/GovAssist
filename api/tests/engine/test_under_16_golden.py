"""Golden test set for `passport-under-16` — mirrors the other Phase 9
services' test structure."""

import pytest

from app.engine.resolver import UNDER_16_SERVICE_CODE, resolve_case
from tests.engine.under_16_golden_scenarios import UNDER_16_GOLDEN_SCENARIOS


@pytest.mark.parametrize(
    "scenario", UNDER_16_GOLDEN_SCENARIOS, ids=[s["name"] for s in UNDER_16_GOLDEN_SCENARIOS]
)
def test_under_16_golden_scenario(db, scenario):
    result = resolve_case(db, scenario["answers"], service_code=UNDER_16_SERVICE_CODE)

    # The whole point of this service: an under-16 age must NOT trigger
    # the scope gate here, unlike every other service.
    assert result.scope_gate is None, scenario["name"]

    actual_labels = {r.label for r in result.requirements}
    assert actual_labels == scenario["expected_labels"], scenario["name"]

    assert result.fee.base_amount == scenario["expected_fee"], scenario["name"]

    actual_offices = {o.name for o in result.offices.offices}
    assert actual_offices == scenario["expected_offices"], scenario["name"]


def test_under_16_scope_gate_exempted_but_other_services_still_gate(db):
    """Confirms the fix is scoped correctly — passport-under-16 accepts
    an under-16 age, but every other service still refuses one."""
    from app.engine.resolver import RENEWAL_SERVICE_CODE

    under_16 = resolve_case(
        db, {**{k: v for k, v in UNDER_16_GOLDEN_SCENARIOS[0]["answers"].items()}, "age": "8"},
        service_code=UNDER_16_SERVICE_CODE,
    )
    assert under_16.scope_gate is None

    renewal_answers = {
        "age": "8", "applying_from": "sri_lanka", "holds_passport": "true",
        "name_changed": "false", "dual_citizen": "false", "section_19_2": "false",
        "profession": "", "buddhist_priest": "false", "district": "Colombo",
        "service_basis": "normal",
    }
    renewal = resolve_case(db, renewal_answers, service_code=RENEWAL_SERVICE_CODE)
    assert renewal.scope_gate is not None


def test_every_requirement_and_fee_has_a_citation(db):
    for scenario in UNDER_16_GOLDEN_SCENARIOS:
        result = resolve_case(db, scenario["answers"], service_code=UNDER_16_SERVICE_CODE)
        for r in result.requirements:
            assert r.citation.source_document_id and r.citation.source_url, (
                f"{scenario['name']}: {r.label!r} has no citation"
            )
        assert result.fee.citation.source_document_id, f"{scenario['name']}: fee has no citation"
