"""6.11.1 tool-wrapper unit tests: malformed-argument handling."""

from app.chat.tools import call_tool


def test_unknown_tool_name_returns_structured_error(db):
    result = call_tool(db, "not_a_real_tool", {})
    assert "error" in result


def test_missing_required_argument_returns_structured_error(db):
    # get_fee requires both "service" and "urgency" — omit "urgency".
    result = call_tool(db, "get_fee", {"service": "renewal"})
    assert "error" in result


def test_wrong_typed_argument_does_not_raise(db):
    # find_office requires "urgent" to be present; omit it entirely so
    # the handler's dict lookup raises KeyError internally.
    result = call_tool(db, "find_office", {"district": "Kandy"})
    assert "error" in result


def test_unknown_service_value_returns_structured_error(db):
    result = call_tool(db, "get_fee", {"service": "bogus", "urgency": "normal"})
    assert "error" in result
