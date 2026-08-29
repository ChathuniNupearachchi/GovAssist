"""Golden test set for `passport-new` (first-time applicant) — mirrors
`test_golden.py`'s structure, run against `resolve_case`'s new
`service_code` parameter instead of its renewal default."""

import pytest

from app.engine.resolver import NEW_APPLICANT_SERVICE_CODE, resolve_case
from tests.engine.new_applicant_golden_scenarios import NEW_APPLICANT_GOLDEN_SCENARIOS


@pytest.mark.parametrize(
    "scenario", NEW_APPLICANT_GOLDEN_SCENARIOS, ids=[s["name"] for s in NEW_APPLICANT_GOLDEN_SCENARIOS]
)
def test_new_applicant_golden_scenario(db, scenario):
    result = resolve_case(db, scenario["answers"], service_code=NEW_APPLICANT_SERVICE_CODE)

    if scenario["expect_scope_gate"]:
        assert result.scope_gate is not None
        return

    assert result.scope_gate is None

    actual_labels = {r.label for r in result.requirements}
    assert actual_labels == scenario["expected_labels"], scenario["name"]

    assert result.fee.base_amount == scenario["expected_fee"], scenario["name"]

    actual_offices = {o.name for o in result.offices.offices}
    assert actual_offices == scenario["expected_offices"], scenario["name"]

    assert (result.amendment_alternative is not None) == scenario.get(
        "expect_amendment_alternative", False
    ), scenario["name"]


def test_no_current_passport_item_in_any_scenario(db):
    """The one structural difference from renewal design.md is explicit
    about: no current-passport document, ever, for a first-time
    applicant — checked directly rather than only implied by the
    per-scenario expected_labels sets above."""
    for scenario in NEW_APPLICANT_GOLDEN_SCENARIOS:
        if scenario["expect_scope_gate"]:
            continue
        result = resolve_case(db, scenario["answers"], service_code=NEW_APPLICANT_SERVICE_CODE)
        labels = {r.label for r in result.requirements}
        assert not any("current passport" in label.lower() for label in labels), (
            f"{scenario['name']}: unexpected current-passport item in {labels}"
        )


def test_nic_gated_on_age_for_standard_set(db):
    """design.md's flagged nuance: an under-16 first-time applicant
    (were the scope gate ever lifted) shouldn't be asked for an NIC they
    can't have yet. Checked directly against the standard-set NIC
    Requirement's own condition, not inferred — age < 16 already hits
    the scope gate in every real call, so this exercises the Condition
    the same way `resolve_requirements` does, at the boundary."""
    from app.engine.conditions import condition_link_passes
    from app.engine.resolver import _approved_rule_version
    from app.models import Requirement, RequirementCondition
    from sqlalchemy import select

    # Scoped to passport-new's own RuleVersion — renewal seeds a
    # Requirement with this exact label too (unconditional there), so
    # an unscoped label lookup could return either service's row.
    rule_version = _approved_rule_version(db, NEW_APPLICANT_SERVICE_CODE)
    nic_requirement = db.scalars(
        select(Requirement).where(
            Requirement.rule_version_id == rule_version.id,
            Requirement.label == "Original National Identity Card of the applicant with a photocopy",
        )
    ).first()
    assert nic_requirement is not None
    links = db.scalars(
        select(RequirementCondition).where(RequirementCondition.requirement_id == nic_requirement.id)
    ).all()
    assert links, "NIC requirement should have at least one gating condition (age >= 16)"

    below_16 = {"age": "15", "dual_citizen": "false"}
    at_16 = {"age": "16", "dual_citizen": "false"}
    assert all(condition_link_passes(l.condition, l.negated, at_16) for l in links)
    assert not all(condition_link_passes(l.condition, l.negated, below_16) for l in links)
