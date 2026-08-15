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
