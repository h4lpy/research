import json

from parser import mutation_log

from .fixtures import C0B4, EA2C, read


def _jsonl(*entries) -> str:
    return "\n".join(json.dumps(e) for e in entries)


def test_kind1_set_and_kind2_push_basic():
    text = _jsonl(
        {"kind": 0, "v": {"items": []}},
        {"kind": 2, "k": ["items"], "v": [{"a": 1}, {"a": 2}]},
        {"kind": 1, "k": ["items", 0, "a"], "v": 99},
    )
    result = mutation_log.replay(text)
    assert result["state"] == {"items": [{"a": 99}, {"a": 2}]}
    assert result["warnings"] == []


def test_kind2_push_with_truncate_and_append():
    text = _jsonl(
        {"kind": 0, "v": {"items": [1, 2, 3, 4]}},
        {"kind": 2, "k": ["items"], "v": [9, 10], "i": 1},
    )
    result = mutation_log.replay(text)
    assert result["state"]["items"] == [1, 9, 10]


def test_kind2_pure_truncate_with_no_v():
    text = _jsonl(
        {"kind": 0, "v": {"items": [1, 2, 3]}},
        {"kind": 2, "k": ["items"], "i": 1},
    )
    result = mutation_log.replay(text)
    assert result["state"]["items"] == [1]


def test_kind3_delete():
    text = _jsonl(
        {"kind": 0, "v": {"a": 1, "b": 2}},
        {"kind": 3, "k": ["a"]},
    )
    result = mutation_log.replay(text)
    assert result["state"] == {"b": 2}


def test_provenance_tracks_line_numbers():
    text = _jsonl(
        {"kind": 0, "v": {"items": []}},
        {"kind": 2, "k": ["items"], "v": [1]},
        {"kind": 1, "k": ["items", 0], "v": 2},
    )
    result = mutation_log.replay(text)
    assert result["provenance"][""] == [1]
    assert result["provenance"]["items"] == [2]
    assert result["provenance"]["items/0"] == [3]


def test_real_kind2_truncation_request4_line32():
    """ea2c0634 line 32: a response array truncated to 2 items then extended -
    a mid-stream rewrite of the model's own response, not a plain append."""
    text = read(EA2C)
    lines = text.split("\n")
    line32 = json.loads(lines[31])
    assert line32["kind"] == 2 and line32["i"] == 2
    pushed_count = len(line32["v"])

    before = mutation_log.replay(text, max_line=31)["state"]
    assert len(before["requests"][4]["response"]) > 2

    after = mutation_log.replay(text)["state"]
    assert len(after["requests"][4]["response"]) == 2 + pushed_count


def test_real_kind2_truncation_request5_line42():
    text = read(EA2C)
    lines = text.split("\n")
    line42 = json.loads(lines[41])
    assert line42["kind"] == 2 and line42["i"] == 1
    pushed_count = len(line42["v"])

    after = mutation_log.replay(text)["state"]
    assert len(after["requests"][5]["response"]) == 1 + pushed_count


def test_request_source_lines_attributes_a_pushed_request_to_its_push_line():
    """Regression: a kind:2 push onto ["requests"] only records the array's
    path, not the index(es) it landed at - provenance must still trace a
    pushed (not initial-snapshot) request back to the line that pushed it."""
    text = _jsonl(
        {"kind": 0, "v": {"requests": [{"requestId": "r0"}]}},
        {"kind": 2, "k": ["requests"], "v": [{"requestId": "r1"}, {"requestId": "r2"}]},
        {"kind": 1, "k": ["requests", 1, "modelState"], "v": {"value": 1}},
    )
    result = mutation_log.replay(text)
    initial_count = result["initial_requests_count"]

    assert mutation_log.request_source_lines(result["ops"], 0, initial_count) == [1]
    assert mutation_log.request_source_lines(result["ops"], 1, initial_count) == [2, 3]
    assert mutation_log.request_source_lines(result["ops"], 2, initial_count) == [2]


def test_request_source_lines_real_session_pushed_request():
    """c0b4f2ea: request 1 is pushed whole at line 14, not part of the
    kind:0 snapshot - its source lines must point at line 14, not line 1."""
    text = read(C0B4)
    result = mutation_log.replay(text)
    lines = mutation_log.request_source_lines(result["ops"], 1, result["initial_requests_count"])
    assert lines == [14]


def test_missing_initial_entry_still_replays():
    text = _jsonl({"kind": 1, "k": ["a"], "v": 1})
    result = mutation_log.replay(text)
    assert result["state"] == {"a": 1}
    assert any(w["type"] == "missing_initial_entry" for w in result["warnings"])


def test_unknown_kind_is_recorded_and_skipped():
    text = _jsonl(
        {"kind": 0, "v": {"a": 1}},
        {"kind": 9, "k": ["a"], "v": 2},
    )
    result = mutation_log.replay(text)
    assert result["state"] == {"a": 1}
    assert any(w["type"] == "unknown_kind" for w in result["warnings"])


def test_truncation_marker_is_flagged():
    text = _jsonl(
        {"kind": 0, "v": {}},
        {"kind": 1, "k": ["big"], "v": "[VS Code: value truncated for persistence, 2MB]"},
    )
    result = mutation_log.replay(text)
    assert any(w["type"] == "truncated_value" for w in result["warnings"])
