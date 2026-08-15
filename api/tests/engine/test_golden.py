"""15.2 Golden test set — runs the real resolver against every one of the
ten BACKEND_PLAN.md Phase 4.7 scenarios and asserts the hand-verified
expected output. A regression in any single scenario fails the suite
(see tasks.md 15.3 for the verified-regression check)."""

import pytest

from app.engine.resolver import resolve_case
from tests.engine.golden_scenarios import GOLDEN_SCENARIOS


@pytest.mark.parametrize(
    "scenario", GOLDEN_SCENARIOS, ids=[s["name"] for s in GOLDEN_SCENARIOS]
)
def test_golden_scenario(db, scenario):
    result = resolve_case(db, scenario["answers"])

    if scenario["expect_scope_gate"]:
        assert result.scope_gate is not None
        return

    assert result.scope_gate is None

    actual_labels = {r.label for r in result.requirements}
    assert actual_labels == scenario["expected_labels"], scenario["name"]

    assert result.fee.base_amount == scenario["expected_fee"], scenario["name"]

    actual_offices = {o.name for o in result.offices.offices}
    assert actual_offices == scenario["expected_offices"], scenario["name"]

    assert (result.offices.conflict_note is not None) == scenario[
        "expect_conflict_note"
    ], scenario["name"]

    assert (result.amendment_alternative is not None) == scenario[
        "expect_amendment_alternative"
    ], scenario["name"]
