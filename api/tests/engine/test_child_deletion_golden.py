"""Golden test set for `passport-child-deletion` — mirrors the other
Phase 9 services' test structure."""

import pytest

from app.engine.resolver import CHILD_DELETION_SERVICE_CODE, resolve_case
from tests.engine.child_deletion_golden_scenarios import CHILD_DELETION_GOLDEN_SCENARIOS


@pytest.mark.parametrize(
    "scenario", CHILD_DELETION_GOLDEN_SCENARIOS, ids=[s["name"] for s in CHILD_DELETION_GOLDEN_SCENARIOS]
)
def test_child_deletion_golden_scenario(db, scenario):
    result = resolve_case(db, scenario["answers"], service_code=CHILD_DELETION_SERVICE_CODE)

    assert result.scope_gate is None
    assert {r.label for r in result.requirements} == scenario["expected_labels"], scenario["name"]
    assert result.fee.base_amount == 1200.00, scenario["name"]
    assert {o.name for o in result.offices.offices} == scenario["expected_offices"], scenario["name"]
    assert result.amendment_alternative is None, scenario["name"]


def test_form_is_form_c_not_form_o(db):
    """Conflict 3's resolution, checked directly: this service must
    cite child_deletion_application.pdf, never amendment.pdf."""
    from tests.engine.child_deletion_golden_scenarios import CHILD_DELETION_GOLDEN_SCENARIOS

    for scenario in CHILD_DELETION_GOLDEN_SCENARIOS:
        result = resolve_case(db, scenario["answers"], service_code=CHILD_DELETION_SERVICE_CODE)
        form = next(r for r in result.requirements if "Form C" in r.label)
        resource_urls = "".join(res["url"] for res in (form.resources or []))
        assert "child_deletion_application.pdf" in resource_urls, scenario["name"]
        assert "amendment.pdf" not in resource_urls, scenario["name"]


def test_every_requirement_and_fee_has_a_citation(db):
    for scenario in CHILD_DELETION_GOLDEN_SCENARIOS:
        result = resolve_case(db, scenario["answers"], service_code=CHILD_DELETION_SERVICE_CODE)
        for r in result.requirements:
            assert r.citation.source_document_id and r.citation.source_url, (
                f"{scenario['name']}: {r.label!r} has no citation"
            )
        assert result.fee.citation.source_document_id, f"{scenario['name']}: fee has no citation"
