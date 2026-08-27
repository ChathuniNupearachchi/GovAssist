"""Golden test set for `passport-lost-stolen` — mirrors
`test_new_applicant_golden.py`'s structure."""

import pytest

from app.engine.resolver import LOST_STOLEN_SERVICE_CODE, resolve_case
from tests.engine.lost_stolen_golden_scenarios import LOST_STOLEN_GOLDEN_SCENARIOS, NMRP_LABEL


@pytest.mark.parametrize(
    "scenario", LOST_STOLEN_GOLDEN_SCENARIOS, ids=[s["name"] for s in LOST_STOLEN_GOLDEN_SCENARIOS]
)
def test_lost_stolen_golden_scenario(db, scenario):
    result = resolve_case(db, scenario["answers"], service_code=LOST_STOLEN_SERVICE_CODE)

    assert result.scope_gate is None

    actual_labels = {r.label for r in result.requirements}
    assert actual_labels == scenario["expected_labels"], scenario["name"]

    assert result.fee.base_amount == scenario["expected_fee"], scenario["name"]

    actual_offices = {o.name for o in result.offices.offices}
    assert actual_offices == scenario["expected_offices"], scenario["name"]

    assert result.amendment_alternative is None, scenario["name"]


def test_nmrp_only_required_when_lost_abroad(db):
    """NMRP tracks `lost_location`, NOT `applying_from` — scenario 6
    (lost abroad, now applying domestically) is the case that
    distinguishes them; asserting against applying_from here would
    reintroduce the bug that prompted separating the two attributes."""
    for scenario in LOST_STOLEN_GOLDEN_SCENARIOS:
        result = resolve_case(db, scenario["answers"], service_code=LOST_STOLEN_SERVICE_CODE)
        labels = {r.label for r in result.requirements}
        expects_nmrp = scenario["answers"].get("lost_location") == "abroad"
        assert (NMRP_LABEL in labels) == expects_nmrp, (
            f"{scenario['name']}: NMRP presence should match lost_location=='abroad'"
        )


def test_every_requirement_and_fee_has_a_citation(db):
    for scenario in LOST_STOLEN_GOLDEN_SCENARIOS:
        result = resolve_case(db, scenario["answers"], service_code=LOST_STOLEN_SERVICE_CODE)
        for r in result.requirements:
            assert r.citation.source_document_id and r.citation.source_url, (
                f"{scenario['name']}: {r.label!r} has no citation"
            )
        assert result.fee.citation.source_document_id, f"{scenario['name']}: fee has no citation"
