"""10.2 Fee calculator unit tests — both bases, with citation."""

from app.engine.fees import resolve_fee
from app.models import RuleVersion, Service


def _renewal_rule_version_id(db):
    service = db.query(Service).filter(Service.code == "passport-renewal").first()
    return (
        db.query(RuleVersion)
        .filter(RuleVersion.service_id == service.id, RuleVersion.status == "approved")
        .first()
        .id
    )


def test_normal_fee(db):
    rv_id = _renewal_rule_version_id(db)
    fee = resolve_fee(db, rv_id, basis="normal")
    assert fee.base_amount == 10000.00
    assert fee.citation.source_url.endswith("id=8")


def test_urgent_fee(db):
    rv_id = _renewal_rule_version_id(db)
    fee = resolve_fee(db, rv_id, basis="urgent")
    assert fee.base_amount == 20000.00
    assert fee.citation.source_url.endswith("id=8")


def test_below_16_fee_tier(db):
    # langgraph-orchestration-branch: the below-16 tier reuses the same
    # age Condition the fingerprints requirement already links —
    # FeeRule.condition_id, not a new column. `resolve_fee` takes a full
    # `answers` dict now (generalized for lost/stolen's penalty tiers —
    # Phase 9 service #3 — see app.engine.fees's own docstring), not a
    # bare `age` value.
    rv_id = _renewal_rule_version_id(db)
    assert resolve_fee(db, rv_id, basis="normal", answers={"age": "10"}).base_amount == 3000.00
    assert resolve_fee(db, rv_id, basis="urgent", answers={"age": "10"}).base_amount == 9000.00


def test_age_16_gets_the_adult_tier_not_the_below_16_tier(db):
    rv_id = _renewal_rule_version_id(db)
    assert resolve_fee(db, rv_id, basis="normal", answers={"age": "16"}).base_amount == 10000.00


def test_no_age_given_defaults_to_the_adult_tier(db):
    rv_id = _renewal_rule_version_id(db)
    assert resolve_fee(db, rv_id, basis="normal", answers=None).base_amount == 10000.00
