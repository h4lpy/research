from parser.parse import parse_session

from .fixtures import EEBA, read


def test_zero_request_session_then_one_pushed():
    text = read(EEBA)
    parsed = parse_session(text, "eeba4cf4-74fa-417e-86ba-bf4990fe4c03.jsonl")
    assert len(parsed["requests"]) == 1


def test_incomplete_request_flagged_not_errored():
    text = read(EEBA)
    parsed = parse_session(text, "eeba4cf4-74fa-417e-86ba-bf4990fe4c03.jsonl")
    req = parsed["requests"][0]
    assert req["is_incomplete"] is True
    assert req["model_state_value"] == 0
    assert "result" not in req["raw"]
    # the answer stops mid-sentence - that is expected for an incomplete request
    assert req["response_markdown"].endswith("help with the next ")

    types = [w["type"] for w in parsed["warnings"]]
    assert "incomplete_request" in types
    assert "invalid_json" not in types
    assert "op_apply_error" not in types


def test_auto_mode_resolution_and_account():
    text = read(EEBA)
    parsed = parse_session(text, "eeba4cf4-74fa-417e-86ba-bf4990fe4c03.jsonl")
    req = parsed["requests"][0]
    assert req["auto_mode_resolution"]["resolvedModel"] == "mai-code-1.1-flash"
    assert parsed["session"]["account_label"] == "h4lpy"
    assert parsed["session"]["custom_title"] == "Chat initialization test"
    assert parsed["session"]["selected_model_is_auto_placeholder"] is True


def test_filename_session_id_match_and_mismatch():
    text = read(EEBA)
    matching = parse_session(text, "eeba4cf4-74fa-417e-86ba-bf4990fe4c03.jsonl")
    mismatched = parse_session(text, "renamed-copy.jsonl")

    assert not any(w["type"] == "filename_session_id_mismatch" for w in matching["warnings"])
    assert any(w["type"] == "filename_session_id_mismatch" for w in mismatched["warnings"])


def test_empty_requests_session_is_flagged_as_valid_not_an_error():
    text = '{"kind":0,"v":{"sessionId":"x","requests":[]}}\n'
    parsed = parse_session(text, "x.jsonl")
    assert parsed["requests"] == []
    assert any(w["type"] == "zero_requests" for w in parsed["warnings"])
