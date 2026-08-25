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


def test_message_with_surrounding_prose_does_not_match():
    """A message with more than a bare type-appropriate answer must fall
    through to the Claude classifier — see the intent-classification
    spec's "message with surrounding prose" scenario."""
    assert try_deterministic_match("age", "I am 34 years old") is None
    assert try_deterministic_match("district", "I live in Kandy") is None
    assert try_deterministic_match("holds_passport", "yes I do") is None


def test_unknown_attribute_never_matches():
    assert try_deterministic_match("not_a_real_attribute", "anything") is None
