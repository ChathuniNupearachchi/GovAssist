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
# Seven-corrections round, item 1 — see golden_scenarios.py's own
# FINGERPRINTS_OVERSEAS_LABEL for the full rationale.
FINGERPRINTS_OVERSEAS_LABEL = (
    "On your first arrival in Sri Lanka after your passport is issued, "
    "complete a Biometric Data Acquisition (BDA) form at the airport, "
    "then report to the Head Office or a Regional Office to give your "
    "fingerprints"
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
        "answers": {**BASE, "age": "30", "district": "Colombo", "photo_district": "Colombo"},
        "expected_labels": CORE_ADULT,
        "expected_fee": 10000.00,
        "expected_offices": {"Head Office"},
        "expect_scope_gate": False,
    },
    {
        "name": "2. Same but urgent",
        "answers": {**BASE, "age": "30", "district": "Colombo", "photo_district": "Colombo", "service_basis": "urgent"},
        "expected_labels": CORE_ADULT,
        "expected_fee": 20000.00,
        "expected_offices": {"Head Office"},
        "expect_scope_gate": False,
    },
    {
        "name": "3. Applying from abroad — Mission-only offices and form",
        "answers": {**BASE, "age": "30", "district": None, "applying_from": "abroad"},
        # Conversational-quality round, item 3: no photo studio
        # acknowledgement overseas.
        "expected_labels": (CORE_ADULT - {APPLICATION_FORM_LABEL, FINGERPRINTS_LABEL, "Photo studio acknowledgement"})
        | {OVERSEAS_APPLICATION_FORM_LABEL, FINGERPRINTS_OVERSEAS_LABEL},
        # Seven-corrections round, item 5.
        "expected_fee": 158.00,
        "expected_currency": "USD",
        "expected_offices": {"Overseas Sri Lankan Missions"},
        "expect_scope_gate": False,
    },
    {
        "name": "4. Under-16 — scope gate, not a partial plan",
        "answers": {**BASE, "age": "10", "district": "Colombo", "photo_district": "Colombo"},
        "expected_labels": set(),
        "expected_fee": None,
        "expected_offices": set(),
        "expect_scope_gate": True,
    },
    {
        "name": "5. Exactly 16 — NIC's lower boundary, still included",
        "answers": {**BASE, "age": "16", "district": "Colombo", "photo_district": "Colombo"},
        "expected_labels": CORE_ADULT,
        "expected_fee": 10000.00,
        "expected_offices": {"Head Office"},
        "expect_scope_gate": False,
    },
    {
        "name": "6. Dual citizen",
        "answers": {**BASE, "age": "30", "district": "Colombo", "photo_district": "Colombo", "dual_citizen": "true"},
        "expected_labels": DUAL_CITIZEN_SET,
        "expected_fee": 10000.00,
        "expected_offices": {"Head Office"},
        "expect_scope_gate": False,
    },
    {
        # Seven-corrections round, item 2: name_changed is no longer part
        # of this service's question set at all ("Has your name changed
        # SINCE YOUR PASSPORT WAS ISSUED?" presupposes a prior passport a
        # first-time applicant doesn't have — see
        # app.engine.renewal_intake's NEW_APPLICANT_QUESTIONS comment).
        # A stray "name_changed" answer (e.g. leftover from a prior
        # service in the same conversation) must have NO effect here —
        # no marriage certificate, same core set as scenario 1. This
        # scenario used to expect the opposite; rewritten to lock in the
        # corrected behavior rather than deleted, so a regression back
        # to the old wholesale-reuse-from-renewal bug would be caught.
        "name": "7. A stray name_changed answer has no effect (item 2 regression)",
        "answers": {**BASE, "age": "30", "district": "Colombo", "photo_district": "Colombo", "name_changed": "true"},
        "expected_labels": CORE_ADULT,
        "expected_fee": 10000.00,
        "expected_offices": {"Head Office"},
        "expect_scope_gate": False,
        "expect_amendment_alternative": False,
    },
    {
        "name": "8. Buddhist priest",
        "answers": {**BASE, "age": "30", "district": "Colombo", "photo_district": "Colombo", "buddhist_priest": "true"},
        "expected_labels": CORE_ADULT | {SAMANERA_LABEL},
        "expected_fee": 10000.00,
        "expected_offices": {"Head Office"},
        "expect_scope_gate": False,
    },
]

assert len(NEW_APPLICANT_GOLDEN_SCENARIOS) == 8
