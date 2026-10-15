from parser import mutation_log
from parser.parse import parse_session

from .fixtures import C0B4, EA2C, EEBA, C0B4_WITH_FILE, read


def test_write_order_differs_from_event_order_but_state_is_coherent():
    """c0b4f2ea: request 0's completion fields (kind:1, lines 4-12) are written
    before its answer text (kind:2, line 13) - replay must still produce a
    complete, correct record regardless of that write order."""
    text = read(C0B4)
    parsed = parse_session(text, "c0b4f2ea-e8d3-4d29-bf8c-25fca694f539.jsonl")
    req0 = parsed["requests"][0]
    assert req0["model_state_value"] == 1
    assert req0["is_incomplete"] is False
    assert req0["elapsed_ms"] == 4945
    assert "Hello world! How can I help today?" in req0["response_markdown"]


def test_request_pushed_whole_in_one_line():
    text = read(C0B4)
    parsed = parse_session(text, "c0b4f2ea-e8d3-4d29-bf8c-25fca694f539.jsonl")
    req1 = parsed["requests"][1]
    assert req1["elapsed_ms"] == 2299
    assert req1["model_state_value"] == 1


def test_single_push_can_add_multiple_requests_at_once():
    """ea2c0634 line 15 pushes four requests in one line: three already
    complete, one left pending to be patched by later lines."""
    text = read(EA2C)
    result = mutation_log.replay(text)
    push = next(op for op in result["ops"] if op["line"] == 15)
    assert push["kind"] == 2
    assert push["path"] == ["requests"]

    requests = result["state"]["requests"]
    assert len(requests) == 7
    assert requests[1]["modelState"]["value"] == 1
    assert requests[2]["modelState"]["value"] == 1
    assert requests[3]["modelState"]["value"] == 1


def test_title_can_arrive_before_or_after_the_request_push():
    # eeba4cf4: customTitle (line 3) arrives after the request push (line 2)
    eeba_result = mutation_log.replay(read(EEBA))
    title_line = eeba_result["provenance"]["customTitle"][0]
    request_push_line = eeba_result["provenance"]["requests"][0]
    assert title_line > request_push_line

    # c0b4f2ea: customTitle (line 2) arrives before the request push (line 3)
    c0b4_result = mutation_log.replay(read(C0B4))
    title_line = c0b4_result["provenance"]["customTitle"][0]
    request_push_line = c0b4_result["provenance"]["requests"][0]
    assert title_line < request_push_line


def test_timestamp_out_of_order_detection_synthetic_regression():
    import json

    text = "\n".join([
        json.dumps({"kind": 0, "v": {"requests": []}}),
        json.dumps({"kind": 2, "k": ["requests"], "v": [{"timestamp": 1000}]}),
        json.dumps({"kind": 1, "k": ["requests", 0, "responseTimestamp"], "v": 500}),
    ])
    result = mutation_log.replay(text)
    assert any(w["type"] == "timestamp_out_of_order" for w in result["warnings"])


def test_timestamp_out_of_order_clean_on_simple_real_sessions():
    for path in (EEBA, C0B4, C0B4_WITH_FILE):
        result = mutation_log.replay(read(path))
        assert not any(w["type"] == "timestamp_out_of_order" for w in result["warnings"])


def test_timestamp_out_of_order_appears_on_the_tool_call_session():
    """ea2c0634 has terminal commands needing user approval, so a round's own
    timestamp can read earlier than an already-seen terminal-confirmation
    timestamp from the same or an earlier line - a real, expected interleaving,
    not necessarily evidence of tampering."""
    result = mutation_log.replay(read(EA2C))
    assert any(w["type"] == "timestamp_out_of_order" for w in result["warnings"])
