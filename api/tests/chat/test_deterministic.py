from app.chat.deterministic import try_deterministic_match


def test_bare_district_name_matches():
    assert try_deterministic_match("district", "Kandy") == "Kandy"
    assert try_deterministic_match("district", "  kandy  ") == "Kandy"


def test_unrecognized_district_does_not_match():
    assert try_deterministic_match("district", "Narnia") is None


def test_bare_numeric_age_matches():
    assert try_deterministic_match("age", "34") == "34"


def test_non_numeric_age_does_not_match():
    assert try_deterministic_match("age", "thirty-four") is None


def test_bare_boolean_yes_no_matches():
    assert try_deterministic_match("holds_passport", "yes") == "true"
    assert try_deterministic_match("holds_passport", "No") == "false"


def test_boolean_attribute_rejects_non_lexicon_word():
    assert try_deterministic_match("holds_passport", "maybe") is None


def test_service_basis_synonyms_match():
    assert try_deterministic_match("service_basis", "urgent") == "urgent"
    assert try_deterministic_match("service_basis", "same-day") == "urgent"
    assert try_deterministic_match("service_basis", "regular") == "normal"


def test_profession_always_accepts_free_text():
    assert try_deterministic_match("profession", "Software Engineer") == "Software Engineer"


def test_blank_profession_records_as_no_profession():
    """Bug fix (manual QA bug #4): the prompt says "leave blank if you
    don't have one" — a blank or whitespace-only message must record as
    "" (no profession), the same convention golden-scenario fixtures
    already use, not fall through to the classifier and effectively be
    dropped."""
    assert try_deterministic_match("profession", "") == ""
    assert try_deterministic_match("profession", "   ") == ""


def test_message_with_surrounding_prose_still_matches():
    """CRITICAL BUG FIX (production incident): a message with a plausible
    answer embedded in a normal sentence must match deterministically,
    with no LLM call — the old contract (bare tokens only) is what
    caused "I am 20 years old" to loop forever asking the age question.
    See this change's own report for the full incident writeup."""
    assert try_deterministic_match("age", "I am 34 years old") == "34"
    assert try_deterministic_match("age", "im 20") == "20"
    assert try_deterministic_match("age", "I'm 20 years old thanks") == "20"
    assert try_deterministic_match("age", "age 20") == "20"
    assert try_deterministic_match("district", "I live in Kandy") == "Kandy"
    assert try_deterministic_match("district", "I'm from Colombo district") == "Colombo"
    assert try_deterministic_match("district", "I am in Colombo district") == "Colombo"
    assert try_deterministic_match("holds_passport", "yes I do") == "true"
    assert try_deterministic_match("holds_passport", "yes I still have it") == "true"
    assert try_deterministic_match("holds_passport", "no I don't have it anymore") == "false"
    assert try_deterministic_match("holds_passport", "I do") == "true"
    assert try_deterministic_match("holds_passport", "I don't") == "false"
    assert try_deterministic_match("applying_from", "I'm from Sri Lanka") == "sri_lanka"
    assert try_deterministic_match("applying_from", "here in sri lanka") == "sri_lanka"
    assert try_deterministic_match("applying_from", "I'm abroad") == "abroad"
    assert try_deterministic_match("applying_from", "not in sri lanka") == "abroad"
    # A named country/city with no explicit sri-lanka/abroad phrasing
    # isn't handled deterministically — that generalization stays with
    # the classifier (now Claude Haiku — see item 4 of this change).
    assert try_deterministic_match("applying_from", "I am currently in Dubai") is None
    assert try_deterministic_match("service_basis", "I need it urgently") == "urgent"
    assert try_deterministic_match("service_basis", "normal is fine") == "normal"
    assert try_deterministic_match("service_basis", "30 days is fine") == "normal"


def test_unrelated_prose_still_does_not_match():
    """A message that isn't a plausible answer at all (no digits, no
    yes/no lexicon, no known phrase) still falls through to the
    classifier — widening the matcher doesn't mean it accepts anything."""
    assert try_deterministic_match("age", "not sure yet") is None
    assert try_deterministic_match("holds_passport", "maybe, I'll check") is None
    assert try_deterministic_match("district", "somewhere in the south") is None


def test_a_question_mentioning_a_keyword_does_not_deterministically_match():
    """Bug found and fixed during this change's own live verification: a
    genuine question that happens to mention a matcher's keyword must
    fall through to the classifier (which detects it's a question and
    routes to the agent), never get silently recorded as if it were an
    answer — the exact ticket-mandated verification case."""
    assert try_deterministic_match("service_basis", "what's the difference between normal and urgent") is None
    assert try_deterministic_match("service_basis", "which is faster, normal or urgent?") is None
    assert try_deterministic_match("applying_from", "what happens if I'm abroad?") is None
    assert try_deterministic_match("district", "which district has the fastest office?") is None
    # Still matches when it's a genuine answer, not a question.
    assert try_deterministic_match("service_basis", "I need it urgently") == "urgent"


def test_unknown_attribute_never_matches():
    assert try_deterministic_match("not_a_real_attribute", "anything") is None
