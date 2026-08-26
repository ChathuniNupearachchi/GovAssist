"""Golden scenarios for `passport-new` (first-time applicant, design.md
service #2) — a smaller set than renewal's 24, covering only what's
actually different about this service: no current-passport item, the
applying_from-conditional form/office split (same mechanism renewal's
own re-verification built), and the NIC-conditional-on-age nuance
design.md flags as first-time-specific. Everything else (dual citizen,
buddhist priest, section 19(2), profession) reuses the exact same
condition machinery renewal's 24 scenarios already exercise thoroughly,
so isn't re-covered exhaustively here.
"""

BASE = {
    "name_changed": "false",
    "dual_citizen": "false",
    "section_19_2": "false",
    "profession": "",
    "buddhist_priest": "false",
    "service_basis": "normal",
    "applying_from": "sri_lanka",
}

FINGERPRINTS_LABEL = (
    "Provide fingerprints in person at the Head Office or a Regional "
    "Office (required for applicants aged 16 to 60)"
)
APPLICATION_FORM_LABEL = "Completed application form K-35A"
OVERSEAS_APPLICATION_FORM_LABEL = "Completed Overseas Missions Passport Application form"
BIRTH_CERT_LABEL = "Original Birth Certificate of the applicant with a photocopy."
NIC_LABEL = "Original National Identity Card of the applicant with a photocopy"
# No CURRENT_PASSPORT_LABEL here at all — design.md: a first-time
# applicant has no prior passport to submit, by definition.
CORE_ADULT = {
    "Photo studio acknowledgement", APPLICATION_FORM_LABEL, FINGERPRINTS_LABEL,
    BIRTH_CERT_LABEL, NIC_LABEL,
}
MARRIAGE_CERT_LABEL = (
    "Marriage certificate with a photocopy where it is necessary "
    "(to confirm the name after marriage)"
)
SAMANERA_LABEL = (
    "Samanera certificate or Higher Ordination certificate, "
    "with photocopies (mandatory for Buddhist priests)"
)
DUAL_CITIZEN_SET = {
    "Photo studio acknowledgement", APPLICATION_FORM_LABEL, FINGERPRINTS_LABEL,
    "Dual Citizenship Certificate with a photocopy.",
    "Foreign passport with any Sri Lankan passport if there is (with photocopy of Bio data pages)",
    "National Identity Card with a photocopy.",
    "Birth Certificate with a photocopy.",
}

NEW_APPLICANT_GOLDEN_SCENARIOS = [
    {
        "name": "1. Straightforward first-time applicant, Colombo, normal",
        "answers": {**BASE, "age": "30", "district": "Colombo"},
        "expected_labels": CORE_ADULT,
        "expected_fee": 10000.00,
        "expected_offices": {"Head Office"},
        "expect_scope_gate": False,
    },
    {
        "name": "2. Same but urgent",
        "answers": {**BASE, "age": "30", "district": "Colombo", "service_basis": "urgent"},
        "expected_labels": CORE_ADULT,
        "expected_fee": 20000.00,
        "expected_offices": {"Head Office"},
        "expect_scope_gate": False,
    },
    {
        "name": "3. Applying from abroad — Mission-only offices and form",
        "answers": {**BASE, "age": "30", "district": None, "applying_from": "abroad"},
        "expected_labels": (CORE_ADULT - {APPLICATION_FORM_LABEL}) | {OVERSEAS_APPLICATION_FORM_LABEL},
        "expected_fee": 10000.00,
        "expected_offices": {"Overseas Sri Lankan Missions"},
        "expect_scope_gate": False,
    },
    {
        "name": "4. Under-16 — scope gate, not a partial plan",
        "answers": {**BASE, "age": "10", "district": "Colombo"},
        "expected_labels": set(),
        "expected_fee": None,
        "expected_offices": set(),
        "expect_scope_gate": True,
    },
    {
        "name": "5. Exactly 16 — NIC's lower boundary, still included",
        "answers": {**BASE, "age": "16", "district": "Colombo"},
        "expected_labels": CORE_ADULT,
        "expected_fee": 10000.00,
        "expected_offices": {"Head Office"},
        "expect_scope_gate": False,
    },
    {
        "name": "6. Dual citizen",
        "answers": {**BASE, "age": "30", "district": "Colombo", "dual_citizen": "true"},
        "expected_labels": DUAL_CITIZEN_SET,
        "expected_fee": 10000.00,
        "expected_offices": {"Head Office"},
        "expect_scope_gate": False,
    },
    {
        "name": "7. Name changed — marriage cert present, no amendment alternative",
        "answers": {**BASE, "age": "30", "district": "Colombo", "name_changed": "true"},
        "expected_labels": CORE_ADULT | {MARRIAGE_CERT_LABEL},
        "expected_fee": 10000.00,
        "expected_offices": {"Head Office"},
        "expect_scope_gate": False,
        # The one explicit non-parity check with renewal: a first-time
        # applicant has nothing existing to amend, so no
        # amendment_alternative regardless of name_changed — see
        # app.engine.resolver.resolve_case's service_code check.
        "expect_amendment_alternative": False,
    },
    {
        "name": "8. Buddhist priest",
        "answers": {**BASE, "age": "30", "district": "Colombo", "buddhist_priest": "true"},
        "expected_labels": CORE_ADULT | {SAMANERA_LABEL},
        "expected_fee": 10000.00,
        "expected_offices": {"Head Office"},
        "expect_scope_gate": False,
    },
]

assert len(NEW_APPLICANT_GOLDEN_SCENARIOS) == 8
