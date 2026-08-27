"""Golden test set for `emergency-certificate` — mirrors the other
Phase 9 services' test structure. Every scenario uses the same flat
LKR 500 fee (no urgent tier exists), checked once rather than repeated
per scenario."""

import pytest

from app.engine.resolver import EMERGENCY_CERTIFICATE_SERVICE_CODE, resolve_case
from tests.engine.emergency_certificate_golden_scenarios import EMERGENCY_CERTIFICATE_GOLDEN_SCENARIOS


@pytest.mark.parametrize(
    "scenario", EMERGENCY_CERTIFICATE_GOLDEN_SCENARIOS,
    ids=[s["name"] for s in EMERGENCY_CERTIFICATE_GOLDEN_SCENARIOS],
)
def test_emergency_certificate_golden_scenario(db, scenario):
    result = resolve_case(db, scenario["answers"], service_code=EMERGENCY_CERTIFICATE_SERVICE_CODE)

    assert result.scope_gate is None
    assert {r.label for r in result.requirements} == scenario["expected_labels"], scenario["name"]
    assert result.fee.base_amount == 500.00, scenario["name"]
    assert {o.name for o in result.offices.offices} == scenario["expected_offices"], scenario["name"]
    assert result.amendment_alternative is None, scenario["name"]


def test_under_16_still_scope_gated_for_emergency_certificate(db):
    """Emergency Certificate is NOT passport-under-16 — the standard
    scope gate must still refuse an under-16 age here, unlike the one
    service built specifically to accept it."""
    result = resolve_case(
        db, {"age": "10", "applying_from": "sri_lanka", "district": "Colombo"},
        service_code=EMERGENCY_CERTIFICATE_SERVICE_CODE,
    )
    assert result.scope_gate is not None


def test_every_requirement_and_fee_has_a_citation(db):
    for scenario in EMERGENCY_CERTIFICATE_GOLDEN_SCENARIOS:
        result = resolve_case(db, scenario["answers"], service_code=EMERGENCY_CERTIFICATE_SERVICE_CODE)
        for r in result.requirements:
            assert r.citation.source_document_id and r.citation.source_url, (
                f"{scenario['name']}: {r.label!r} has no citation"
            )
        assert result.fee.citation.source_document_id, f"{scenario['name']}: fee has no citation"
