"""Golden scenarios for `passport-lost-stolen` (design.md service #3).
Same reduced-set convention as `new_applicant_golden_scenarios.py` —
covers what's actually different about this service (the reporting
prerequisite split, the NMRP condition, the combined penalty fee), not
every condition interaction already exhaustively covered by renewal's
24 scenarios.

Scenario 6 exercises the reason `lost_location` exists as its own
attribute, separate from `applying_from` — a citizen who lost the
passport abroad but has since returned and is applying domestically.
Gating the NMRP/reporting on `applying_from` instead (the original,
wrong implementation) would have silently skipped both for this
citizen — see `app.engine.renewal_intake`'s `_LOST_LOCATION_QUESTION`
docstring.
"""

BASE = {
    "name_changed": "false",
    "dual_citizen": "false",
    "section_19_2": "false",
    "profession": "",
    "buddhist_priest": "false",
    "service_basis": "normal",
    "applying_from": "sri_lanka",
    "lost_location": "sri_lanka",
}

FINGERPRINTS_LABEL = (
    "Provide fingerprints in person at the Head Office or a Regional "
    "Office (required for applicants aged 16 to 60)"
)
APPLICATION_FORM_LABEL = "Completed application form K-35A"
OVERSEAS_APPLICATION_FORM_LABEL = "Completed Overseas Missions Passport Application form"
POLICE_COMPLAINT_LABEL = "Original of the police complaint, including the lost passport number"
NMRP_LABEL = "Temporary travel document (NMRP) used to arrive in Sri Lanka, with a photocopy"
DOMESTIC_REPORTING_LABEL = (
    "Report the loss or theft: call the Immigration Department "
    "hotline (0112 101 533, or fax 011-2885358, 8.30am-4.00pm "
    "Mon-Fri excluding government holidays) AND make a complaint "
    "to your local police station as soon as possible"
)
OVERSEAS_REPORTING_LABEL = (
    "Report the loss or theft: obtain a police report from your "
    "local police in your country of residence, download and "
    "complete the stolen/lost passport complaint form, and "
    "submit both together to the nearest Sri Lankan Diplomatic "
    "or Consular office"
)
BIRTH_CERT_LABEL = "Original Birth Certificate of the applicant with a photocopy."
NIC_LABEL = "Original National Identity Card of the applicant with a photocopy"
MARRIAGE_CERT_LABEL = (
    "Marriage certificate with a photocopy where it is necessary "
    "(to confirm the name after marriage)"
)

CORE_DOMESTIC = {
    "Photo studio acknowledgement", APPLICATION_FORM_LABEL, FINGERPRINTS_LABEL,
    BIRTH_CERT_LABEL, NIC_LABEL, POLICE_COMPLAINT_LABEL, DOMESTIC_REPORTING_LABEL,
}
CORE_OVERSEAS = {
    "Photo studio acknowledgement", OVERSEAS_APPLICATION_FORM_LABEL, FINGERPRINTS_LABEL,
    BIRTH_CERT_LABEL, NIC_LABEL, POLICE_COMPLAINT_LABEL, OVERSEAS_REPORTING_LABEL, NMRP_LABEL,
}

LOST_STOLEN_GOLDEN_SCENARIOS = [
    {
        "name": "1. Domestic, lost within a year, normal",
        "answers": {**BASE, "age": "30", "district": "Colombo", "photo_district": "Colombo", "lost_passport_age": "within_1_year"},
        "expected_labels": CORE_DOMESTIC,
        "expected_fee": 30000.00,  # 10,000 base + 20,000 penalty
        "expected_offices": {"Head Office"},
    },
    {
        "name": "2. Domestic, lost over a year ago, normal",
        "answers": {**BASE, "age": "30", "district": "Colombo", "photo_district": "Colombo", "lost_passport_age": "over_1_year"},
        "expected_labels": CORE_DOMESTIC,
        "expected_fee": 25000.00,  # 10,000 base + 15,000 penalty
        "expected_offices": {"Head Office"},
    },
    {
        "name": "3. Domestic, lost within a year, urgent",
        "answers": {
            **BASE, "age": "30", "district": "Colombo", "photo_district": "Colombo",
            "lost_passport_age": "within_1_year", "service_basis": "urgent",
        },
        "expected_labels": CORE_DOMESTIC,
        "expected_fee": 40000.00,  # 20,000 base + 20,000 penalty
        "expected_offices": {"Head Office"},
    },
    {
        "name": "4. Applying from abroad, lost abroad — Mission-only offices/form, NMRP required",
        "answers": {
            **BASE, "age": "30", "district": None, "applying_from": "abroad",
            "lost_location": "abroad", "lost_passport_age": "over_1_year",
        },
        "expected_labels": CORE_OVERSEAS,
        "expected_fee": 25000.00,
        "expected_offices": {"Overseas Sri Lankan Missions"},
    },
    {
        "name": "5. Name changed — marriage cert present alongside the loss documents",
        "answers": {
            **BASE, "age": "30", "district": "Colombo", "photo_district": "Colombo", "name_changed": "true",
            "lost_passport_age": "within_1_year",
        },
        "expected_labels": CORE_DOMESTIC | {MARRIAGE_CERT_LABEL},
        "expected_fee": 30000.00,
        "expected_offices": {"Head Office"},
    },
    {
        # Lost abroad, but already returned and applying domestically
        # (flew home on the NMRP) — the case that exposed lost_location
        # as its own attribute. NMRP and the OVERSEAS reporting
        # instructions still apply (the loss/reporting happened abroad);
        # the application form and office are domestic (applying_from
        # is now sri_lanka).
        "name": "6. Lost abroad, now applying domestically — NMRP still required",
        "answers": {
            **BASE, "age": "30", "district": "Colombo", "photo_district": "Colombo", "applying_from": "sri_lanka",
            "lost_location": "abroad", "lost_passport_age": "within_1_year",
        },
        "expected_labels": {
            "Photo studio acknowledgement", APPLICATION_FORM_LABEL, FINGERPRINTS_LABEL,
            BIRTH_CERT_LABEL, NIC_LABEL, POLICE_COMPLAINT_LABEL, OVERSEAS_REPORTING_LABEL,
            NMRP_LABEL,
        },
        "expected_fee": 30000.00,
        "expected_offices": {"Head Office"},
    },
]

assert len(LOST_STOLEN_GOLDEN_SCENARIOS) == 6
