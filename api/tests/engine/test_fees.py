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
    # FeeRule.condition_id, not a new column.
    rv_id = _renewal_rule_version_id(db)
    assert resolve_fee(db, rv_id, basis="normal", age=10).base_amount == 3000.00
    assert resolve_fee(db, rv_id, basis="urgent", age=10).base_amount == 9000.00


def test_age_16_gets_the_adult_tier_not_the_below_16_tier(db):
    rv_id = _renewal_rule_version_id(db)
    assert resolve_fee(db, rv_id, basis="normal", age=16).base_amount == 10000.00


def test_no_age_given_defaults_to_the_adult_tier(db):
    rv_id = _renewal_rule_version_id(db)
    assert resolve_fee(db, rv_id, basis="normal", age=None).base_amount == 10000.00
