"""Golden scenarios for `emergency-certificate` (design.md service #7,
the last of the seven). No `service_basis` (no urgent tier exists for
this fee) and no alteration-type/family-circumstance style question —
design.md is explicit that no source states a document list specific
to this certificate beyond the K-35A form; Requirements here are
limited to what's independently, generally sourced (the form, photo
studio acknowledgement, fingerprints, and an explicit scope note)."""

ELIGIBILITY_NOTE_LABEL = (
    "This Emergency Certificate is valid ONLY for travel to India or "
    "Nepal (Buddhist pilgrimage) — it is not a general travel document "
    "and cannot be used for travel to any other country"
)
APPLICATION_FORM_LABEL = "Completed application form K-35A (tick 'Emergency Certificates (India and Nepal)')"
OVERSEAS_APPLICATION_FORM_LABEL = "Completed Overseas Missions Passport Application form (tick 'Emergency/Identity Certificate')"
STUDIO_ACK_LABEL = "Photo studio acknowledgement"
FINGERPRINTS_LABEL = (
    "Provide fingerprints in person at the Head Office or a Regional "
    "Office (required for applicants aged 16 to 60)"
)

CORE_DOMESTIC = {ELIGIBILITY_NOTE_LABEL, APPLICATION_FORM_LABEL, STUDIO_ACK_LABEL, FINGERPRINTS_LABEL}

EMERGENCY_CERTIFICATE_GOLDEN_SCENARIOS = [
    {
        "name": "1. Domestic, adult",
        "answers": {"age": "30", "applying_from": "sri_lanka", "district": "Colombo", "photo_district": "Colombo"},
        "expected_labels": CORE_DOMESTIC,
        "expected_offices": {"Head Office"},
    },
    {
        "name": "2. Domestic, exactly 16 — fingerprints included",
        "answers": {"age": "16", "applying_from": "sri_lanka", "district": "Colombo", "photo_district": "Colombo"},
        "expected_labels": CORE_DOMESTIC,
        "expected_offices": {"Head Office"},
    },
    {
        "name": "3. Domestic, exactly 61 — fingerprints excluded",
        "answers": {"age": "61", "applying_from": "sri_lanka", "district": "Colombo", "photo_district": "Colombo"},
        "expected_labels": CORE_DOMESTIC - {FINGERPRINTS_LABEL},
        "expected_offices": {"Head Office"},
    },
    {
        "name": "4. Applying from abroad — Mission-only offices/form",
        "answers": {"age": "30", "applying_from": "abroad", "district": None},
        "expected_labels": (CORE_DOMESTIC - {APPLICATION_FORM_LABEL}) | {OVERSEAS_APPLICATION_FORM_LABEL},
        "expected_offices": {"Overseas Sri Lankan Missions"},
    },
]

assert len(EMERGENCY_CERTIFICATE_GOLDEN_SCENARIOS) == 4
