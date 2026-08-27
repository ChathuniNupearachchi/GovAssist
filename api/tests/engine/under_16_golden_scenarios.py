"""Golden scenarios for `passport-under-16` (design.md service #5).
Covers the base case, each special-circumstance branch independently,
the applying_from-driven form/office split, and one scenario combining
several special circumstances at once (the case that most risks a
resolver bug — set-replacement/independence errors are exactly what
renewal's own dual-citizen-plus-buddhist-priest scenario was built to
catch, see `tests/engine/golden_scenarios.py`).
"""

BASE = {
    "parents_hold_passport": "true",
    "child_previously_in_parent_passport": "false",
    "parent_circumstance": "none",
    "child_adopted": "false",
    "child_born_overseas": "false",
    "service_basis": "normal",
    "applying_from": "sri_lanka",
}

BOTH_PARENTS_ATTEND_LABEL = (
    "Both parents, or the legal guardian, must be present to hand over the application in person"
)
APPLICATION_FORM_LABEL = "Completed application form K-35A"
OVERSEAS_APPLICATION_FORM_LABEL = "Completed Overseas Missions Passport Application form"
STUDIO_ACK_LABEL = "Photo studio acknowledgement"
BIRTH_CERT_LABEL = "Original birth certificate of the child, with a photocopy"
PARENTS_PASSPORT_LABEL = (
    "Parents' passports, with photocopies of the data page and the page showing the child's particulars"
)
PARENTS_NO_PASSPORT_LABEL = (
    "National Identity Cards of both parents, with photocopies, and an "
    "affidavit confirming the parents do not hold a valid Sri Lankan passport"
)
CONSENT_LETTER_LABEL = "Consent letter of the parents (or legal guardian)"
CURRENT_PASSPORT_LABEL = "Current passport with a photocopy of the Bio data page, if the child already has one"
DELETION_FIRST_LABEL = (
    "The child's name must first be removed from the parent's passport before a "
    "separate passport can be issued (Form I.E. 35C, LKR 1,200) — complete this before applying here"
)
DECEASED_LABEL = (
    "Original death certificate(s), the surviving parent's or legal guardian's "
    "identification document, the guardian's consent letter, and a report from "
    "the Grama Niladhari attested by the Divisional Secretary"
)
DIVORCED_LABEL = "Original divorce certificate and the court order stating custody of the child"
ABANDONED_LABEL = (
    "Certified copy of the police report and a confirmation letter from the "
    "Grama Niladhari, countersigned by the Divisional Secretary"
)
ADOPTION_LABEL = (
    "Certificate of Adoption, the court order, and a letter from the "
    "Commissioner of Probation and Child Care"
)
CITIZENSHIP_CERT_LABEL = (
    "Sri Lankan Citizenship certificate issued by the Department of "
    "Immigration and Emigration, with a photocopy"
)

CORE = {
    BOTH_PARENTS_ATTEND_LABEL, APPLICATION_FORM_LABEL, STUDIO_ACK_LABEL,
    BIRTH_CERT_LABEL, PARENTS_PASSPORT_LABEL, CONSENT_LETTER_LABEL, CURRENT_PASSPORT_LABEL,
}

UNDER_16_GOLDEN_SCENARIOS = [
    {
        "name": "1. Straightforward case, domestic, 10-year normal",
        "answers": {**BASE, "age": "10", "district": "Colombo", "photo_district": "Colombo", "validity_period": "10_year"},
        "expected_labels": CORE,
        "expected_fee": 10000.00,
        "expected_offices": {"Head Office"},
    },
    {
        "name": "2. Same but 3-year validity, urgent",
        "answers": {
            **BASE, "age": "10", "district": "Colombo", "photo_district": "Colombo",
            "validity_period": "3_year", "service_basis": "urgent",
        },
        "expected_labels": CORE,
        "expected_fee": 9000.00,
        "expected_offices": {"Head Office"},
    },
    {
        "name": "3. Parents don't hold a valid passport",
        "answers": {
            **BASE, "age": "8", "district": "Colombo", "photo_district": "Colombo", "validity_period": "10_year",
            "parents_hold_passport": "false",
        },
        "expected_labels": (CORE - {PARENTS_PASSPORT_LABEL}) | {PARENTS_NO_PASSPORT_LABEL},
        "expected_fee": 10000.00,
        "expected_offices": {"Head Office"},
    },
    {
        "name": "4. Child previously in a parent's passport — deletion-first prerequisite",
        "answers": {
            **BASE, "age": "12", "district": "Colombo", "photo_district": "Colombo", "validity_period": "10_year",
            "child_previously_in_parent_passport": "true",
        },
        "expected_labels": CORE | {DELETION_FIRST_LABEL},
        "expected_fee": 10000.00,
        "expected_offices": {"Head Office"},
    },
    {
        "name": "5. Deceased parent",
        "answers": {
            **BASE, "age": "10", "district": "Colombo", "photo_district": "Colombo", "validity_period": "10_year",
            "parent_circumstance": "deceased",
        },
        "expected_labels": CORE | {DECEASED_LABEL},
        "expected_fee": 10000.00,
        "expected_offices": {"Head Office"},
    },
    {
        "name": "6. Divorced parents",
        "answers": {
            **BASE, "age": "10", "district": "Colombo", "photo_district": "Colombo", "validity_period": "10_year",
            "parent_circumstance": "divorced",
        },
        "expected_labels": CORE | {DIVORCED_LABEL},
        "expected_fee": 10000.00,
        "expected_offices": {"Head Office"},
    },
    {
        "name": "7. Abandoned child",
        "answers": {
            **BASE, "age": "10", "district": "Colombo", "photo_district": "Colombo", "validity_period": "10_year",
            "parent_circumstance": "abandoned",
        },
        "expected_labels": CORE | {ABANDONED_LABEL},
        "expected_fee": 10000.00,
        "expected_offices": {"Head Office"},
    },
    {
        "name": "8. Adopted child",
        "answers": {
            **BASE, "age": "10", "district": "Colombo", "photo_district": "Colombo", "validity_period": "10_year",
            "child_adopted": "true",
        },
        "expected_labels": CORE | {ADOPTION_LABEL},
        "expected_fee": 10000.00,
        "expected_offices": {"Head Office"},
    },
    {
        "name": "9. Born overseas",
        "answers": {
            **BASE, "age": "10", "district": "Colombo", "photo_district": "Colombo", "validity_period": "10_year",
            "child_born_overseas": "true",
        },
        "expected_labels": CORE | {CITIZENSHIP_CERT_LABEL},
        "expected_fee": 10000.00,
        "expected_offices": {"Head Office"},
    },
    {
        "name": "10. Applying from abroad — Mission-only offices/form",
        "answers": {
            **BASE, "age": "10", "district": None, "applying_from": "abroad",
            "validity_period": "10_year",
        },
        "expected_labels": (CORE - {APPLICATION_FORM_LABEL}) | {OVERSEAS_APPLICATION_FORM_LABEL},
        "expected_fee": 10000.00,
        "expected_offices": {"Overseas Sri Lankan Missions"},
    },
    {
        "name": "11. Everything at once — deceased parent, adopted, born overseas, "
        "previously in parent's passport, no valid parent passport, abroad, 3yr urgent",
        "answers": {
            **BASE, "age": "6", "district": None, "applying_from": "abroad",
            "validity_period": "3_year", "service_basis": "urgent",
            "parents_hold_passport": "false", "child_previously_in_parent_passport": "true",
            "parent_circumstance": "deceased", "child_adopted": "true", "child_born_overseas": "true",
        },
        "expected_labels": {
            BOTH_PARENTS_ATTEND_LABEL, OVERSEAS_APPLICATION_FORM_LABEL, STUDIO_ACK_LABEL,
            BIRTH_CERT_LABEL, PARENTS_NO_PASSPORT_LABEL, CONSENT_LETTER_LABEL, CURRENT_PASSPORT_LABEL,
            DELETION_FIRST_LABEL, DECEASED_LABEL, ADOPTION_LABEL, CITIZENSHIP_CERT_LABEL,
        },
        "expected_fee": 9000.00,
        "expected_offices": {"Overseas Sri Lankan Missions"},
    },
]

assert len(UNDER_16_GOLDEN_SCENARIOS) == 11
