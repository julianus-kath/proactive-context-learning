from langgraph_integration.contracts.response_envelope import ErrorInfo, ResponseEnvelope


def test_response_envelope_coerces_rows_field():
    envelope = ResponseEnvelope.model_validate(
        {"ok": True, "rows": [{"value": 1}], "row_count": 1}
    )
    assert envelope.data == [{"value": 1}]
    assert envelope.row_count == 1


def test_response_envelope_normalizes_warnings():
    envelope = ResponseEnvelope.model_validate(
        {"ok": True, "data": [], "warnings": "slow query"}
    )
    assert envelope.warnings == ["slow query"]


def test_error_info_from_string_message():
    error = ErrorInfo.model_validate("Timeout occurred")
    assert error.type == "UNKNOWN_ERROR"
    assert error.message == "Timeout occurred"


def test_response_envelope_fills_growth_defaults():
    envelope = ResponseEnvelope.model_validate(
        {"ok": False, "data": [], "error": "Query failed"}
    )
    assert envelope.error_info is not None
    assert envelope.error_info.message == "Query failed"

