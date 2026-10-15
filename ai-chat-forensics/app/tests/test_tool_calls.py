from parser import tool_calls as tool_calls_mod
from parser.parse import parse_session

from .fixtures import C0B4_WITH_FILE, EA2C, read


def test_toolid_and_round_name_are_different_strings_and_get_joined():
    text = read(C0B4_WITH_FILE)
    parsed = parse_session(text, "c0b4f2ea-e8d3-4d29-bf8c-25fca694f539_with_file.jsonl")
    calls = parsed["requests"][2]["tool_calls"]
    assert len(calls) == 1

    call = calls[0]
    assert call["tool_id"] == "copilot_readFile"
    assert call["round_name"] == "read_file"
    assert call["tool_id"] != call["round_name"]
    assert call["arguments"]["filePath"].endswith("README.md")
    assert call["is_confirmed_type"] == 1
    assert call["vscode_seed"] == 1792049432767


def test_node_tree_result_flattened_to_text():
    text = read(C0B4_WITH_FILE)
    parsed = parse_session(text, "c0b4f2ea-e8d3-4d29-bf8c-25fca694f539_with_file.jsonl")
    result = parsed["requests"][2]["tool_calls"][0]["result"]
    assert result["kind"] == "node_tree"
    # the real node has lineBreakBefore:true on its one text leaf
    assert result["text"] == "\n# Experiments"


def test_terminal_tool_call_fields():
    text = read(EA2C)
    parsed = parse_session(text, "ea2c0634-0eb0-4923-94be-78a3e4236710.jsonl")
    terminal_calls = [
        c for req in parsed["requests"] for c in req["tool_calls"] if c["is_terminal"]
    ]
    assert terminal_calls

    call = terminal_calls[0]
    assert call["tool_id"] == "run_in_terminal"
    assert call["is_confirmed_type"] == 4
    assert call["terminal"]["command_original"]
    assert call["terminal"]["command_timestamp"] is not None


def test_isConfirmed_type_1_and_4_both_seen():
    text = read(EA2C)
    parsed = parse_session(text, "ea2c0634-0eb0-4923-94be-78a3e4236710.jsonl")
    types_seen = {c["is_confirmed_type"] for req in parsed["requests"] for c in req["tool_calls"]}
    assert 1 in types_seen
    assert 4 in types_seen


def test_plain_string_tool_result_is_not_mistaken_for_a_node_tree():
    text = read(EA2C)
    parsed = parse_session(text, "ea2c0634-0eb0-4923-94be-78a3e4236710.jsonl")
    create_dir_calls = [
        c for req in parsed["requests"] for c in req["tool_calls"]
        if c["tool_id"] == "copilot_createDirectory"
    ]
    assert create_dir_calls
    assert create_dir_calls[0]["result"]["kind"] == "string"
    assert "Created directory" in create_dir_calls[0]["result"]["text"]


def test_flatten_tool_result_plain_string():
    raw = {"$mid": 20, "content": [{"$mid": 21, "value": "Created directory at C:\\x"}]}
    assert tool_calls_mod.flatten_tool_result(raw) == {
        "kind": "string", "text": "Created directory at C:\\x", "raw": raw,
    }


def test_flatten_tool_result_node_tree_respects_line_break_before():
    raw = {
        "$mid": 20,
        "content": [{"$mid": 23, "value": {"node": {
            "type": 1,
            "children": [
                {"type": 2, "text": "line one", "lineBreakBefore": False},
                {"type": 2, "text": "line two", "lineBreakBefore": True},
            ],
        }}}],
    }
    flattened = tool_calls_mod.flatten_tool_result(raw)
    assert flattened["kind"] == "node_tree"
    assert flattened["text"] == "line one\nline two"


def test_flatten_tool_result_missing_and_unknown_shapes_are_safe():
    assert tool_calls_mod.flatten_tool_result(None)["kind"] == "missing"
    assert tool_calls_mod.flatten_tool_result(42)["kind"] == "unknown"
    assert tool_calls_mod.flatten_tool_result({"no": "content key"})["kind"] == "unknown"
