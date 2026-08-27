"""Golden scenarios for `passport-child-deletion` (design.md service
#6) — the shortest service built so far: one form (Form C, NOT the
general alteration Form O — Conflict 3's resolution), one document, one
flat fee, only the domestic/overseas OFFICE split (no form split)."""

APPLICATION_FORM_LABEL = "Completed Children Deletion Application Form (Form C)"
PASSPORT_LABEL = "Passport (the one listing the child to be removed)"

CHILD_DELETION_GOLDEN_SCENARIOS = [
    {
        "name": "1. Domestic, Colombo",
        "answers": {"age": "40", "applying_from": "sri_lanka", "district": "Colombo"},
        "expected_labels": {APPLICATION_FORM_LABEL, PASSPORT_LABEL},
        "expected_offices": {"Head Office"},
    },
    {
        "name": "2. Domestic, Kandy",
        "answers": {"age": "35", "applying_from": "sri_lanka", "district": "Kandy"},
        "expected_labels": {APPLICATION_FORM_LABEL, PASSPORT_LABEL},
        "expected_offices": {"Head Office", "Kandy Regional Office"},
    },
    {
        "name": "3. Applying from abroad — Mission-only offices, SAME form as domestic",
        "answers": {"age": "40", "applying_from": "abroad", "district": None},
        "expected_labels": {APPLICATION_FORM_LABEL, PASSPORT_LABEL},
        "expected_offices": {"Overseas Sri Lankan Missions"},
    },
]

assert len(CHILD_DELETION_GOLDEN_SCENARIOS) == 3
