"""13.2 Next-question logic unit tests."""

from app.engine.next_question import next_question
from app.engine.renewal_intake import ATTRIBUTE_BY_PROMPT


def test_answering_dual_citizen_changes_next_question(renewal_service_id, db):
    answered_up_to_dual_citizen = {
        "age": "30",
        "applying_from": "sri_lanka",
        "holds_passport": "false",
        "name_changed": "false",
    }

    next_if_dual_citizen_true = next_question(
        db, renewal_service_id, {**answered_up_to_dual_citizen, "dual_citizen": "true"}
    )
    next_if_dual_citizen_false = next_question(
        db, renewal_service_id, {**answered_up_to_dual_citizen, "dual_citizen": "false"}
    )

    assert next_if_dual_citizen_true.prompt != next_if_dual_citizen_false.prompt
    # Keyed by attribute, not the prompt's exact wording — see
    # conversational-intake's plain-language audit, which rewrote this
    # question's text away from "section 19(2)" terminology entirely.
    assert ATTRIBUTE_BY_PROMPT[next_if_dual_citizen_true.prompt] == "section_19_2"
    assert ATTRIBUTE_BY_PROMPT[next_if_dual_citizen_false.prompt] != "section_19_2"


def test_no_further_question_once_all_relevant_answered(renewal_service_id, db):
    all_answered = {
        "age": "30",
        "applying_from": "sri_lanka",
        "holds_passport": "false",
        "name_changed": "false",
        "dual_citizen": "false",
        "profession": "",
        "buddhist_priest": "false",
        "district": "Colombo",
        "service_basis": "normal",
    }
    # dual_citizen is false, so section_19_2 is not relevant and should
    # not block "no further question needed"
    assert next_question(db, renewal_service_id, all_answered) is None


def test_age_is_the_first_question(renewal_service_id, db):
    q = next_question(db, renewal_service_id, {})
    assert "old" in q.prompt.lower()
