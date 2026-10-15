from parser.parse import parse_session

from .fixtures import EA2C, read


def test_ea2c0634_replays_cleanly_with_seven_requests():
    text = read(EA2C)
    parsed = parse_session(text, "ea2c0634-0eb0-4923-94be-78a3e4236710.jsonl")

    assert len(parsed["requests"]) == 7
    assert parsed["file"]["line_count"] == 48  # 47 content lines + trailing blank
    assert parsed["file"]["sha256"]
    assert parsed["session"]["account_label"] == "h4lpy"
    assert not any(w["type"] == "filename_session_id_mismatch" for w in parsed["warnings"])

    hard_errors = [
        w for w in parsed["warnings"]
        if w["type"] in ("invalid_json", "op_apply_error", "malformed_entry", "unknown_kind")
    ]
    assert hard_errors == []


def test_every_request_carries_source_lines():
    text = read(EA2C)
    parsed = parse_session(text, "ea2c0634-0eb0-4923-94be-78a3e4236710.jsonl")
    for req in parsed["requests"]:
        assert req["source_lines"], f"request {req['index']} has no source lines"
        assert all(isinstance(n, int) for n in req["source_lines"])


def test_known_anomalies_are_surfaced_not_hidden():
    """This file's kind:0 already contains a non-empty request, which the
    other research samples don't - worth surfacing rather than assuming
    every session starts empty."""
    text = read(EA2C)
    parsed = parse_session(text, "ea2c0634-0eb0-4923-94be-78a3e4236710.jsonl")
    types = [w["type"] for w in parsed["warnings"]]
    assert "initial_snapshot_already_populated" in types
