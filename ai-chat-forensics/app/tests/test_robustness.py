"""Fail-soft behaviour on malformed input - synthetic fixtures only, per
CLAUDE.md (no real case data in tests)."""

import json

from parser.parse import parse_session


def _jsonl(*lines) -> str:
    return "\n".join(lines)


def test_empty_file_does_not_crash():
    parsed = parse_session("", "empty.jsonl")
    assert parsed["requests"] == []
    assert parsed["session"] == {
        "session_id": None, "version": None, "creation_date": None,
        "initial_location": None, "responder_username": None,
        "has_pending_edits": None, "custom_title": None, "account_label": None,
        "selected_model_identifier": None, "selected_model_family": None,
        "selected_model_version": None, "selected_model_is_auto_placeholder": False,
        "model_configuration": None, "input_mode": None, "permission_level": None,
        "pending_requests": [],
    }
    assert any(w["type"] == "zero_requests" for w in parsed["warnings"])


def test_corrupted_middle_line_is_recorded_and_replay_continues():
    text = _jsonl(
        json.dumps({"kind": 0, "v": {"requests": []}}),
        json.dumps({"kind": 2, "k": ["requests"], "v": [{"requestId": "a", "timestamp": 1}]}),
        "{not valid json!!",
        json.dumps({"kind": 2, "k": ["requests"], "v": [{"requestId": "b", "timestamp": 2}]}),
    )
    parsed = parse_session(text, "x.jsonl")
    assert len(parsed["requests"]) == 2
    bad_lines = [w for w in parsed["warnings"] if w["type"] == "invalid_json"]
    assert len(bad_lines) == 1
    assert bad_lines[0]["line"] == 3


def test_file_with_no_kind0_warns_but_still_replays_what_it_can():
    text = _jsonl(
        json.dumps({"kind": 1, "k": ["requests"], "v": []}),
        json.dumps({"kind": 2, "k": ["requests"], "v": [{"requestId": "a", "timestamp": 1}]}),
    )
    parsed = parse_session(text, "x.jsonl")
    assert len(parsed["requests"]) == 1
    assert any(w["type"] == "missing_initial_entry" for w in parsed["warnings"])


def test_very_long_line_does_not_crash():
    big_text = "x" * 2_000_000
    text = _jsonl(
        json.dumps({"kind": 0, "v": {"requests": [{"requestId": "a", "timestamp": 1, "message": {"text": big_text}}]}}),
    )
    parsed = parse_session(text, "x.jsonl")
    assert len(parsed["requests"]) == 1
    assert parsed["requests"][0]["message_text"] == big_text


def test_unknown_response_item_kind_is_shown_not_dropped():
    text = _jsonl(
        json.dumps({"kind": 0, "v": {"requests": [
            {"requestId": "a", "timestamp": 1, "response": [{"kind": "somethingNew", "data": 1}]},
        ]}}),
    )
    parsed = parse_session(text, "x.jsonl")
    req = parsed["requests"][0]
    assert req["response_items"] == [{"kind": "somethingNew", "data": 1}]
    assert any(
        w["type"] == "unknown_response_item_kind" and w["kind"] == "somethingNew"
        for w in parsed["warnings"]
    )


def test_malformed_json_line_with_no_kind_field():
    text = _jsonl(
        json.dumps({"kind": 0, "v": {}}),
        json.dumps({"not_a_kind_field": True}),
    )
    parsed = parse_session(text, "x.jsonl")
    assert any(w["type"] == "malformed_entry" for w in parsed["warnings"])


def test_trailing_blank_line_is_not_an_error():
    text = json.dumps({"kind": 0, "v": {"requests": []}}) + "\n"
    parsed = parse_session(text, "x.jsonl")
    assert not any(w["type"] in ("invalid_json", "malformed_entry") for w in parsed["warnings"])
