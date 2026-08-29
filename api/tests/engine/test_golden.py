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
    # Seven-corrections round, item 5: every scenario predating this fix
    # implicitly expects LKR (the only currency this app ever quoted
    # before) — defaulted so those scenarios don't all need updating.
    assert result.fee.currency == scenario.get("expected_currency", "LKR"), scenario["name"]

    actual_offices = {o.name for o in result.offices.offices}
    assert actual_offices == scenario["expected_offices"], scenario["name"]

    assert (result.offices.conflict_note is not None) == scenario[
        "expect_conflict_note"
    ], scenario["name"]

    assert (result.amendment_alternative is not None) == scenario[
        "expect_amendment_alternative"
    ], scenario["name"]


# The standard set (seq 10-11) and the dual-citizen set (seq 23-24) label
# a birth certificate and an NIC differently — "Original Birth
# Certificate of the applicant with a photocopy." vs "Birth Certificate
# with a photocopy.", and similarly for the NIC — so a plan is checked
# for a document whose label mentions the identity of the passport
# holder's birth/identity record, not one exact string.
def _has_birth_certificate(labels: set[str]) -> bool:
    return any("birth certificate" in label.lower() for label in labels)


def _has_nic(labels: set[str]) -> bool:
    return any("national identity card" in label.lower() for label in labels)


@pytest.mark.parametrize(
    "scenario", GOLDEN_SCENARIOS, ids=[s["name"] for s in GOLDEN_SCENARIOS]
)
def test_every_resolved_plan_includes_birth_certificate_and_nic(db, scenario):
    """Every renewal case — standard set or dual-citizen set — requires
    a birth certificate and an NIC; only the exact label differs by
    branch. A scope-gated (under-16) case produces no plan at all, so it
    is exempt rather than expected to satisfy this."""
    if scenario["expect_scope_gate"]:
        pytest.skip("scope-gated case produces no requirement set")

    result = resolve_case(db, scenario["answers"])
    labels = {r.label for r in result.requirements}

    assert _has_birth_certificate(labels), (
        f"{scenario['name']}: no birth certificate requirement in {labels}"
    )
    assert _has_nic(labels), f"{scenario['name']}: no NIC requirement in {labels}"


@pytest.mark.parametrize(
    "scenario", GOLDEN_SCENARIOS, ids=[s["name"] for s in GOLDEN_SCENARIOS]
)
def test_every_resolved_plan_includes_the_application_form(db, scenario):
    """A citizen must never get a document checklist with no form to
    submit them with — exactly one application-form requirement is
    present in every branch (standard, dual-citizen, or overseas), and
    it's the right variant for `applying_from` (Downloads-page
    re-verification: domestic K-35A vs. the Overseas Missions form —
    see `app.seed.phase4_renewal`)."""
    if scenario["expect_scope_gate"]:
        pytest.skip("scope-gated case produces no requirement set")

    result = resolve_case(db, scenario["answers"])
    form_requirements = [
        r for r in result.requirements if "application form" in r.label.lower()
    ]
    assert len(form_requirements) == 1, (
        f"{scenario['name']}: expected exactly one application form "
        f"requirement, found {[r.label for r in form_requirements]}"
    )
    assert form_requirements[0].resources, (
        f"{scenario['name']}: application form requirement has no resources"
    )
    resource_urls = {r["url"] for r in form_requirements[0].resources}
    joined_urls = "".join(resource_urls)
    if scenario["answers"].get("applying_from") == "abroad":
        assert "new_om_application_form.pdf" in joined_urls
    else:
        assert "passport_application.pdf" in joined_urls
        assert "application.pdf" in joined_urls
        assert "instructions_english_td.pdf" in joined_urls
