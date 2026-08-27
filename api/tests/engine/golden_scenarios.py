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
- Scenario 9 ("applying from abroad") was originally modeled as
  `district = None`, back when Phase 4 didn't model overseas-specific
  office routing at all — the office resolver's behavior for an unknown
  district was "list every Regional Office," an honest placeholder, not
  a real Mission-routing feature. Phase 9's renewal re-verification
  built that feature (a dedicated `applying_from` intake question,
  `app.engine.renewal_intake`) and this scenario now exercises it
  directly: `applying_from = "abroad"`, `district = None` (never asked
  in the real conversational flow — see
  `tests/qa/renewal_conversation_scenarios.py`), and offices narrowed to
  the Mission only, per id=9 seq 2.
"""

BASE = {
    "holds_passport": "true",
    "name_changed": "false",
    "dual_citizen": "false",
    "section_19_2": "false",
    "profession": "",
    "buddhist_priest": "false",
    "service_basis": "normal",
    # Every other scenario is domestic by default — see scenario 9 (the
    # only "abroad" scenario) and 24 (an explicit-domestic regression)
    # for the two applying_from branches Phase 9 added.
    "applying_from": "sri_lanka",
}

FINGERPRINTS_LABEL = (
    "Provide fingerprints in person at the Head Office or a Regional "
    "Office (required for applicants aged 16 to 60)"
)
APPLICATION_FORM_LABEL = "Completed application form K-35A"
# The overseas counterpart — gated on applying_from == "abroad", swapped
# in for APPLICATION_FORM_LABEL rather than added alongside it (see
# scenario 9 below and `app.seed.phase4_renewal`'s two application-form
# Requirements).
OVERSEAS_APPLICATION_FORM_LABEL = "Completed Overseas Missions Passport Application form"
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
EDUCATIONAL_CERT_LABEL = (
    "Educational Certificate related to the profession and an acceptable "
    "document to confirm your service, with photocopies"
)
NEW_NIC_LABEL = (
    "Obtain a new National Identity Card before applying (required for "
    "dual citizenship obtained under section 19(2) of the amended "
    "Citizenship Act 18 of 1948)"
)

GOLDEN_SCENARIOS = [
    {
        "name": "1. Straightforward adult renewal, Colombo, normal",
        "answers": {**BASE, "age": "30", "district": "Colombo", "photo_district": "Colombo"},
        "expected_labels": STANDARD_CORE | {CURRENT_PASSPORT_LABEL},
        "expected_fee": 10000.00,
        "expected_offices": {"Head Office"},
        "expect_conflict_note": False,
        "expect_amendment_alternative": False,
        "expect_scope_gate": False,
    },
    {
        "name": "2. Same but urgent",
        "answers": {**BASE, "age": "30", "district": "Colombo", "photo_district": "Colombo", "service_basis": "urgent"},
        "expected_labels": STANDARD_CORE | {CURRENT_PASSPORT_LABEL},
        "expected_fee": 20000.00,
        "expected_offices": {"Head Office"},
        "expect_conflict_note": True,
        "expect_amendment_alternative": False,
        "expect_scope_gate": False,
    },
    {
        "name": "3. Name changed after marriage",
        "answers": {**BASE, "age": "30", "district": "Colombo", "photo_district": "Colombo", "name_changed": "true"},
        "expected_labels": STANDARD_CORE | {CURRENT_PASSPORT_LABEL, MARRIAGE_CERT_LABEL},
        "expected_fee": 10000.00,
        "expected_offices": {"Head Office"},
        "expect_conflict_note": False,
        "expect_amendment_alternative": True,
        "expect_scope_gate": False,
    },
    {
        "name": "4. Expired over 5 years ago",
        "answers": {**BASE, "age": "40", "district": "Matara", "photo_district": "Matara", "holds_passport": "false"},
        "expected_labels": STANDARD_CORE,
        "expected_fee": 10000.00,
        "expected_offices": {"Head Office", "Matara Regional Office"},
        "expect_conflict_note": False,
        "expect_amendment_alternative": False,
        "expect_scope_gate": False,
    },
    {
        "name": "5. Applying from Kandy",
        "answers": {**BASE, "age": "30", "district": "Kandy", "photo_district": "Kandy"},
        "expected_labels": STANDARD_CORE | {CURRENT_PASSPORT_LABEL},
        "expected_fee": 10000.00,
        "expected_offices": {"Head Office", "Kandy Regional Office"},
        "expect_conflict_note": False,
        "expect_amendment_alternative": False,
        "expect_scope_gate": False,
    },
    {
        "name": "6. Dual citizen",
        "answers": {**BASE, "age": "30", "district": "Colombo", "photo_district": "Colombo", "dual_citizen": "true"},
        "expected_labels": DUAL_CITIZEN_SET,
        "expected_fee": 10000.00,
        "expected_offices": {"Head Office"},
        "expect_conflict_note": False,
        "expect_amendment_alternative": False,
        "expect_scope_gate": False,
    },
    {
        "name": "7. Buddhist priest",
        "answers": {**BASE, "age": "30", "district": "Colombo", "photo_district": "Colombo", "buddhist_priest": "true"},
        "expected_labels": STANDARD_CORE | {CURRENT_PASSPORT_LABEL, SAMANERA_LABEL},
        "expected_fee": 10000.00,
        "expected_offices": {"Head Office"},
        "expect_conflict_note": False,
        "expect_amendment_alternative": False,
        "expect_scope_gate": False,
    },
    {
        "name": "8. No longer holds old passport",
        "answers": {**BASE, "age": "35", "district": "Jaffna", "photo_district": "Jaffna", "holds_passport": "false"},
        "expected_labels": STANDARD_CORE,
        "expected_fee": 10000.00,
        "expected_offices": {"Head Office", "Jaffna Regional Office"},
        "expect_conflict_note": False,
        "expect_amendment_alternative": False,
        "expect_scope_gate": False,
    },
    {
        "name": "9. Applying from abroad",
        "answers": {**BASE, "age": "30", "district": None, "applying_from": "abroad"},
        # STANDARD_CORE's own APPLICATION_FORM_LABEL is domestic-only as
        # of the Downloads-page re-verification — swapped for the
        # Overseas Missions form here, not added alongside it.
        "expected_labels": (STANDARD_CORE - {APPLICATION_FORM_LABEL})
        | {CURRENT_PASSPORT_LABEL, OVERSEAS_APPLICATION_FORM_LABEL},
        "expected_fee": 10000.00,
        # Mission path (id=9 seq 2), not "every office since district is
        # unknown" — see the module docstring's note on this scenario.
        "expected_offices": {"Overseas Sri Lankan Missions"},
        "expect_conflict_note": False,
        "expect_amendment_alternative": False,
        "expect_scope_gate": False,
    },
    {
        "name": "10. Name changed and urgent and Kandy",
        "answers": {
            **BASE, "age": "30", "district": "Kandy", "photo_district": "Kandy",
            "name_changed": "true", "service_basis": "urgent",
        },
        "expected_labels": STANDARD_CORE | {CURRENT_PASSPORT_LABEL, MARRIAGE_CERT_LABEL},
        "expected_fee": 20000.00,
        "expected_offices": {"Head Office", "Kandy Regional Office"},
        "expect_conflict_note": True,
        "expect_amendment_alternative": True,
        "expect_scope_gate": False,
    },
    # -- 11-20: added for langgraph-orchestration-branch's golden set
    # growth (Task Group 3) — deliberately chosen to exercise condition
    # interactions the original ten never touch, found by reading
    # app/seed/phase4_renewal.py's actual condition links rather than
    # guessing: an AND-of-two-conditions requirement (new_nic) whose
    # positive case no scenario had ever hit, both age boundaries of the
    # fingerprint requirement (16-60 inclusive, expressed as two
    # lessThan conditions), the profession-stated branch, and a
    # dual-citizen-replaces-the-standard-set interaction with
    # buddhist_priest that could plausibly double-add a requirement if
    # the resolver's set-replacement logic had a bug.
    {
        "name": "11. Under-16 applicant returns the scope gate",
        "answers": {**BASE, "age": "15", "district": "Colombo", "photo_district": "Colombo"},
        "expected_labels": set(),
        "expected_fee": None,
        "expected_offices": set(),
        "expect_conflict_note": False,
        "expect_amendment_alternative": False,
        "expect_scope_gate": True,
    },
    {
        "name": "12. Exactly 16 — fingerprint requirement's lower boundary",
        "answers": {**BASE, "age": "16", "district": "Colombo", "photo_district": "Colombo"},
        "expected_labels": STANDARD_CORE | {CURRENT_PASSPORT_LABEL},
        "expected_fee": 10000.00,
        "expected_offices": {"Head Office"},
        "expect_conflict_note": False,
        "expect_amendment_alternative": False,
        "expect_scope_gate": False,
    },
    {
        "name": "13. Exactly 60 — fingerprint requirement's upper boundary, still included",
        "answers": {**BASE, "age": "60", "district": "Colombo", "photo_district": "Colombo"},
        "expected_labels": STANDARD_CORE | {CURRENT_PASSPORT_LABEL},
        "expected_fee": 10000.00,
        "expected_offices": {"Head Office"},
        "expect_conflict_note": False,
        "expect_amendment_alternative": False,
        "expect_scope_gate": False,
    },
    {
        "name": "14. Exactly 61 — one past the boundary, fingerprints now excluded",
        "answers": {**BASE, "age": "61", "district": "Colombo", "photo_district": "Colombo"},
        "expected_labels": (STANDARD_CORE | {CURRENT_PASSPORT_LABEL}) - {FINGERPRINTS_LABEL},
        "expected_fee": 10000.00,
        "expected_offices": {"Head Office"},
        "expect_conflict_note": False,
        "expect_amendment_alternative": False,
        "expect_scope_gate": False,
    },
    {
        "name": "15. Dual citizen under section 19(2) — the AND-condition positive case",
        "answers": {
            **BASE, "age": "30", "district": "Colombo", "photo_district": "Colombo",
            "dual_citizen": "true", "section_19_2": "true",
        },
        "expected_labels": DUAL_CITIZEN_SET | {NEW_NIC_LABEL},
        "expected_fee": 10000.00,
        "expected_offices": {"Head Office"},
        "expect_conflict_note": False,
        "expect_amendment_alternative": False,
        "expect_scope_gate": False,
    },
    {
        "name": "16. Section 19(2) alone, not a dual citizen — the AND-condition near-miss",
        "answers": {**BASE, "age": "30", "district": "Colombo", "photo_district": "Colombo", "section_19_2": "true"},
        # new_nic requires BOTH dual_citizen AND section_19_2 — section
        # 19(2) alone must NOT trigger it. A resolver that treated these
        # as an OR (or ignored section_19_2 for a non-dual-citizen case
        # incorrectly) would fail this by including NEW_NIC_LABEL here.
        "expected_labels": STANDARD_CORE | {CURRENT_PASSPORT_LABEL},
        "expected_fee": 10000.00,
        "expected_offices": {"Head Office"},
        "expect_conflict_note": False,
        "expect_amendment_alternative": False,
        "expect_scope_gate": False,
    },
    {
        "name": "17. Profession stated — the educational certificate branch",
        "answers": {**BASE, "age": "30", "district": "Colombo", "photo_district": "Colombo", "profession": "Doctor"},
        "expected_labels": STANDARD_CORE | {CURRENT_PASSPORT_LABEL, EDUCATIONAL_CERT_LABEL},
        "expected_fee": 10000.00,
        "expected_offices": {"Head Office"},
        "expect_conflict_note": False,
        "expect_amendment_alternative": False,
        "expect_scope_gate": False,
    },
    {
        "name": "18. Buddhist priest who is also a dual citizen — the set-replacement near-miss",
        "answers": {
            **BASE, "age": "30", "district": "Colombo", "photo_district": "Colombo",
            "dual_citizen": "true", "buddhist_priest": "true",
        },
        # The Samanera certificate is only linked within the standard
        # document set (itself gated on NOT dual_citizen) — a dual
        # citizen's document set replaces the standard set entirely, so
        # buddhist_priest=true here must NOT add the Samanera
        # certificate. A resolver that evaluated buddhist_priest's
        # condition independently of which set is active would fail
        # this by including it.
        "expected_labels": DUAL_CITIZEN_SET,
        "expected_fee": 10000.00,
        "expected_offices": {"Head Office"},
        "expect_conflict_note": False,
        "expect_amendment_alternative": False,
        "expect_scope_gate": False,
    },
    {
        "name": "19. No current passport and a changed name, together",
        "answers": {
            **BASE, "age": "30", "district": "Vavuniya", "photo_district": "Vavuniya",
            "holds_passport": "false", "name_changed": "true",
        },
        # The marriage certificate's condition (name_changed) is
        # independent of holds_passport — a resolver that conflated "no
        # current passport" with "nothing to confirm the old name
        # against" and dropped the marriage certificate would fail this.
        "expected_labels": STANDARD_CORE | {MARRIAGE_CERT_LABEL},
        "expected_fee": 10000.00,
        "expected_offices": {"Head Office", "Vavuniya Regional Office"},
        "expect_conflict_note": False,
        "expect_amendment_alternative": True,
        "expect_scope_gate": False,
    },
    {
        "name": "20. Everything at once — boundary age, dual citizen, section 19(2), urgent, Kandy",
        "answers": {
            **BASE, "age": "16", "district": "Kandy", "photo_district": "Kandy",
            "dual_citizen": "true", "section_19_2": "true",
            "service_basis": "urgent",
        },
        "expected_labels": DUAL_CITIZEN_SET | {NEW_NIC_LABEL},
        "expected_fee": 20000.00,
        "expected_offices": {"Head Office", "Kandy Regional Office"},
        "expect_conflict_note": True,
        "expect_amendment_alternative": False,
        "expect_scope_gate": False,
    },
    # -- 21-23: added for the manual-QA bug-fix round (Part 1) — each one
    # exercises a specific reported bug against the actual resolver, not
    # just a unit-level assertion, matching this file's own convention.
    {
        "name": "21. Buddhist monk who is also a teacher — bug #6 regression",
        "answers": {
            **BASE, "age": "30", "district": "Colombo", "photo_district": "Colombo",
            "buddhist_priest": "true", "profession": "Teacher",
        },
        # Both the profession-gated Educational Certificate AND the
        # priest-gated Samanera certificate must appear together — a
        # resolver that still (or again) suppressed buddhist_priest once
        # a secular profession was stated would never have recorded
        # buddhist_priest=true in a real intake in the first place; this
        # checks the requirement layer accepts both facts as independent
        # and produces both requirements when they're both true.
        "expected_labels": STANDARD_CORE | {CURRENT_PASSPORT_LABEL, SAMANERA_LABEL, EDUCATIONAL_CERT_LABEL},
        "expected_fee": 10000.00,
        "expected_offices": {"Head Office"},
        "expect_conflict_note": False,
        "expect_amendment_alternative": False,
        "expect_scope_gate": False,
    },
    {
        "name": "22. Colombo applicant — bug #1 regression (no Kurunegala, no Mission)",
        "answers": {**BASE, "age": "30", "district": "Colombo", "photo_district": "Colombo"},
        "expected_labels": STANDARD_CORE | {CURRENT_PASSPORT_LABEL},
        "expected_fee": 10000.00,
        # Exactly Head Office — never Kurunegala Regional Office (~94km
        # away, an implausible placeholder mapping), and never an
        # Overseas Mission for a domestic applicant with a known
        # district.
        "expected_offices": {"Head Office"},
        "expect_conflict_note": False,
        "expect_amendment_alternative": False,
        "expect_scope_gate": False,
    },
    {
        "name": "23. Under-16 applicant — bug #2 regression (scope gate, not a partial plan)",
        "answers": {**BASE, "age": "10", "district": "Colombo", "photo_district": "Colombo"},
        "expected_labels": set(),
        "expected_fee": None,
        "expected_offices": set(),
        "expect_conflict_note": False,
        "expect_amendment_alternative": False,
        "expect_scope_gate": True,
    },
    # -- 24: added for Phase 9's renewal re-verification, alongside
    # scenario 9 above — the two `applying_from` branches (see
    # `app.engine.renewal_intake`). Scenario 9 is "abroad"; every other
    # scenario in this file already defaults to "sri_lanka" via BASE, but
    # this one states it explicitly so the domestic branch has its own
    # named regression the way the abroad branch does, rather than only
    # being implicit in every pre-existing scenario's default.
    {
        "name": "24. Explicit applying_from=sri_lanka — domestic branch (regression)",
        "answers": {**BASE, "age": "30", "district": "Kandy", "photo_district": "Kandy", "applying_from": "sri_lanka"},
        "expected_labels": STANDARD_CORE | {CURRENT_PASSPORT_LABEL},
        "expected_fee": 10000.00,
        "expected_offices": {"Head Office", "Kandy Regional Office"},
        "expect_conflict_note": False,
        "expect_amendment_alternative": False,
        "expect_scope_gate": False,
    },
]

assert len(GOLDEN_SCENARIOS) == 24, "10 original (BACKEND_PLAN.md Phase 4.7) + 10 added for langgraph-orchestration-branch + 3 for the manual-QA bug-fix round + 1 for Phase 9's applying_from domestic-branch regression"
