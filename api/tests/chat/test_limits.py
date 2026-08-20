from app.chat.limits import MAX_MESSAGE_CHARACTERS, truncate_message


def test_message_under_limit_is_unchanged():
    text = "How do I renew my passport?"
    assert truncate_message(text) == text


def test_message_over_limit_is_truncated_before_any_model_call():
    text = "a" * (MAX_MESSAGE_CHARACTERS + 500)
    result = truncate_message(text)
    assert len(result) == MAX_MESSAGE_CHARACTERS
    assert result == "a" * MAX_MESSAGE_CHARACTERS


def test_message_exactly_at_limit_is_unchanged():
    text = "b" * MAX_MESSAGE_CHARACTERS
    assert truncate_message(text) == text
