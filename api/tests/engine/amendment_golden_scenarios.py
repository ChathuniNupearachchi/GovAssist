"""Golden scenarios for `passport-amendment` (design.md service #4).
Covers all 6 buildable alteration types (everything in id=10's table
except "Deletion of a child's name" — its own service, see design.md's
Round 2 correction) and the applying_from-driven office split.
"""

APPLICATION_FORM_LABEL = "Completed Alteration Application Form"
OTHER_AMENDMENTS_LABEL = (
    "Documents required for 'Other Amendments' are not "
    "specified in the Department's published fee table — "
    "confirm directly with the accepting office before "
    "applying"
)

AMENDMENT_GOLDEN_SCENARIOS = [
    {
        "name": "1. Change of name, domestic",
        "answers": {"age": "30", "applying_from": "sri_lanka", "district": "Colombo", "alteration_type": "change_of_name"},
        "expected_labels": {APPLICATION_FORM_LABEL, "Passport", "Marriage certificate (to confirm name change)"},
        "expected_offices": {"Head Office"},
    },
    {
        "name": "2. Profession inclusion, domestic",
        "answers": {"age": "30", "applying_from": "sri_lanka", "district": "Kandy", "alteration_type": "profession_inclusion"},
        "expected_labels": {APPLICATION_FORM_LABEL, "Documents and qualification to prove profession, with photocopies"},
        "expected_offices": {"Head Office", "Kandy Regional Office"},
    },
    {
        "name": "3. NIC number inclusion, domestic",
        "answers": {"age": "30", "applying_from": "sri_lanka", "district": "Colombo", "alteration_type": "nic_inclusion"},
        "expected_labels": {APPLICATION_FORM_LABEL, "National Identity Card, with a photocopy"},
        "expected_offices": {"Head Office"},
    },
    {
        "name": "4. Cancel single journey, domestic",
        "answers": {"age": "30", "applying_from": "sri_lanka", "district": "Colombo", "alteration_type": "cancel_single_journey"},
        "expected_labels": {APPLICATION_FORM_LABEL, "National Identity Card and Birth Certificate, with photocopies"},
        "expected_offices": {"Head Office"},
    },
    {
        "name": "5. Cancel India/Nepal only, domestic",
        "answers": {"age": "30", "applying_from": "sri_lanka", "district": "Colombo", "alteration_type": "cancel_india_nepal"},
        "expected_labels": {APPLICATION_FORM_LABEL, "National Identity Card and Birth Certificate, with photocopies"},
        "expected_offices": {"Head Office"},
    },
    {
        "name": "6. Other amendment, domestic — genuine gap surfaced, not guessed",
        "answers": {"age": "30", "applying_from": "sri_lanka", "district": "Colombo", "alteration_type": "other"},
        "expected_labels": {APPLICATION_FORM_LABEL, OTHER_AMENDMENTS_LABEL},
        "expected_offices": {"Head Office"},
    },
    {
        "name": "7. NIC inclusion, applying from abroad — Mission-only offices, same form",
        "answers": {"age": "30", "applying_from": "abroad", "district": None, "alteration_type": "nic_inclusion"},
        "expected_labels": {APPLICATION_FORM_LABEL, "National Identity Card, with a photocopy"},
        "expected_offices": {"Overseas Sri Lankan Missions"},
    },
]

assert len(AMENDMENT_GOLDEN_SCENARIOS) == 7
