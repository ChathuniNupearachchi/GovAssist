"""15.1 The ten golden scenarios from BACKEND_PLAN.md Phase 4.7.

Each entry is a case's answers plus its hand-verified expected output —
computed by hand against the actual seeded rule data (see
`app.seed.phase4_renewal`), not against the engine itself, so the test
in `test_golden.py` is a real check rather than the engine grading its
own homework.

Two notes on interpretation, recorded here rather than left implicit:
- Scenario 4 ("expired over 5 years ago") is modeled as `holds_passport
  = false` — the source's current-passport requirement is conditioned on
  already holding a *valid* passport, and an expired one is not valid,
  so it should not be requested. Scenario 8 ("no longer holds old
  passport") also resolves to `holds_passport = false`, coincidentally
  producing the same document set for a different real-world reason —
  both are independently hand-verified below rather than assumed equal.
- Scenario 9 ("applying from abroad") is modeled as `district = None`.
  Phase 4 does not model overseas-specific office routing (id=9 was
  ingested but is out of this phase's proposal scope) — the office
  resolver's documented behavior for an unknown district is "list every
  Regional Office," so that is the honestly-expected result here, not an
  overseas-specific narrowing this phase never built.
"""

BASE = {
    "holds_passport": "true",
    "name_changed": "false",
    "dual_citizen": "false",
    "section_19_2": "false",
    "profession": "",
    "buddhist_priest": "false",
    "service_basis": "normal",
}

FINGERPRINTS_LABEL = (
    "Provide fingerprints in person at the Head Office or a Regional "
    "Office (required for applicants aged 16 to 60)"
)
APPLICATION_FORM_LABEL = "Completed application form K-35A"
STANDARD_CORE = {
    "Photo studio acknowledgement",
    APPLICATION_FORM_LABEL,
    FINGERPRINTS_LABEL,
    "Original Birth Certificate of the applicant with a photocopy.",
    "Original National Identity Card of the applicant with a photocopy",
}
CURRENT_PASSPORT_LABEL = "Current passport with a photocopy of the Bio data page."
MARRIAGE_CERT_LABEL = (
    "Marriage certificate with a photocopy where it is necessary "
    "(to confirm the name after marriage)"
)
SAMANERA_LABEL = (
    "Samanera certificate or Higher Ordination certificate, "
    "with photocopies (mandatory for Buddhist priests)"
)
DUAL_CITIZEN_SET = {
    "Photo studio acknowledgement",
    APPLICATION_FORM_LABEL,
    FINGERPRINTS_LABEL,
    "Dual Citizenship Certificate with a photocopy.",
    "Foreign passport with any Sri Lankan passport if there is (with photocopy of Bio data pages)",
    "National Identity Card with a photocopy.",
    "Birth Certificate with a photocopy.",
}
AMENDMENT_DOCS = {"Passport", "Marriage certificate (to confirm name change)"}

GOLDEN_SCENARIOS = [
    {
        "name": "1. Straightforward adult renewal, Colombo, normal",
        "answers": {**BASE, "age": "30", "district": "Colombo"},
        "expected_labels": STANDARD_CORE | {CURRENT_PASSPORT_LABEL},
        "expected_fee": 10000.00,
        "expected_offices": {"Head Office", "Kurunegala Regional Office", "Overseas Sri Lankan Missions"},
        "expect_conflict_note": False,
        "expect_amendment_alternative": False,
        "expect_scope_gate": False,
    },
    {
        "name": "2. Same but urgent",
        "answers": {**BASE, "age": "30", "district": "Colombo", "service_basis": "urgent"},
        "expected_labels": STANDARD_CORE | {CURRENT_PASSPORT_LABEL},
        "expected_fee": 20000.00,
        "expected_offices": {"Head Office", "Kurunegala Regional Office", "Overseas Sri Lankan Missions"},
        "expect_conflict_note": True,
        "expect_amendment_alternative": False,
        "expect_scope_gate": False,
    },
    {
        "name": "3. Name changed after marriage",
        "answers": {**BASE, "age": "30", "district": "Colombo", "name_changed": "true"},
        "expected_labels": STANDARD_CORE | {CURRENT_PASSPORT_LABEL, MARRIAGE_CERT_LABEL},
        "expected_fee": 10000.00,
        "expected_offices": {"Head Office", "Kurunegala Regional Office", "Overseas Sri Lankan Missions"},
        "expect_conflict_note": False,
        "expect_amendment_alternative": True,
        "expect_scope_gate": False,
    },
    {
        "name": "4. Expired over 5 years ago",
        "answers": {**BASE, "age": "40", "district": "Matara", "holds_passport": "false"},
        "expected_labels": STANDARD_CORE,
        "expected_fee": 10000.00,
        "expected_offices": {"Head Office", "Matara Regional Office", "Overseas Sri Lankan Missions"},
        "expect_conflict_note": False,
        "expect_amendment_alternative": False,
        "expect_scope_gate": False,
    },
    {
        "name": "5. Applying from Kandy",
        "answers": {**BASE, "age": "30", "district": "Kandy"},
        "expected_labels": STANDARD_CORE | {CURRENT_PASSPORT_LABEL},
        "expected_fee": 10000.00,
        "expected_offices": {"Head Office", "Kandy Regional Office", "Overseas Sri Lankan Missions"},
        "expect_conflict_note": False,
        "expect_amendment_alternative": False,
        "expect_scope_gate": False,
    },
    {
        "name": "6. Dual citizen",
        "answers": {**BASE, "age": "30", "district": "Colombo", "dual_citizen": "true"},
        "expected_labels": DUAL_CITIZEN_SET,
        "expected_fee": 10000.00,
        "expected_offices": {"Head Office", "Kurunegala Regional Office", "Overseas Sri Lankan Missions"},
        "expect_conflict_note": False,
        "expect_amendment_alternative": False,
        "expect_scope_gate": False,
    },
    {
        "name": "7. Buddhist priest",
        "answers": {**BASE, "age": "30", "district": "Colombo", "buddhist_priest": "true"},
        "expected_labels": STANDARD_CORE | {CURRENT_PASSPORT_LABEL, SAMANERA_LABEL},
        "expected_fee": 10000.00,
        "expected_offices": {"Head Office", "Kurunegala Regional Office", "Overseas Sri Lankan Missions"},
        "expect_conflict_note": False,
        "expect_amendment_alternative": False,
        "expect_scope_gate": False,
    },
    {
        "name": "8. No longer holds old passport",
        "answers": {**BASE, "age": "35", "district": "Jaffna", "holds_passport": "false"},
        "expected_labels": STANDARD_CORE,
        "expected_fee": 10000.00,
        "expected_offices": {"Head Office", "Jaffna Regional Office", "Overseas Sri Lankan Missions"},
        "expect_conflict_note": False,
        "expect_amendment_alternative": False,
        "expect_scope_gate": False,
    },
    {
        "name": "9. Applying from abroad",
        "answers": {**BASE, "age": "30", "district": None},
        "expected_labels": STANDARD_CORE | {CURRENT_PASSPORT_LABEL},
        "expected_fee": 10000.00,
        "expected_offices": {
            "Head Office", "Kandy Regional Office", "Matara Regional Office",
            "Vavuniya Regional Office", "Kurunegala Regional Office",
            "Jaffna Regional Office", "Overseas Sri Lankan Missions",
        },
        "expect_conflict_note": False,
        "expect_amendment_alternative": False,
        "expect_scope_gate": False,
    },
    {
        "name": "10. Name changed and urgent and Kandy",
        "answers": {
            **BASE, "age": "30", "district": "Kandy",
            "name_changed": "true", "service_basis": "urgent",
        },
        "expected_labels": STANDARD_CORE | {CURRENT_PASSPORT_LABEL, MARRIAGE_CERT_LABEL},
        "expected_fee": 20000.00,
        "expected_offices": {"Head Office", "Kandy Regional Office", "Overseas Sri Lankan Missions"},
        "expect_conflict_note": True,
        "expect_amendment_alternative": True,
        "expect_scope_gate": False,
    },
]

assert len(GOLDEN_SCENARIOS) == 10, "BACKEND_PLAN.md Phase 4.7 lists exactly ten scenarios"
