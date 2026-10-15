from parser.artifacts import build_session_artifacts
from parser.parse import parse_session

from .fixtures import C0B4_WITH_FILE, EA2C, read


def test_files_touched_deduplicated_with_actions_and_requests():
    parsed = parse_session(read(EA2C), "ea2c0634-0eb0-4923-94be-78a3e4236710.jsonl")
    artifacts = build_session_artifacts(parsed)
    by_path = {f["path"]: f for f in artifacts["files"]}

    hello = by_path["c:\\dev\\copilot-chat-test\\hello.py"]
    assert hello["actions"] == ["created", "read", "edited", "edited", "edited"]
    assert hello["request_indices"] == [0, 1, 1, 2, 3]
    assert hello["first_seen"] < hello["last_seen"]

    assert by_path["c:\\dev\\copilot-chat-test\\python"]["actions"] == ["created (directory)"]
    assert by_path["c:\\dev\\copilot-chat-test\\python\\hello.py"]["actions"] == ["created"]


def test_terminal_commands_extracted_with_cwd_and_timestamp():
    parsed = parse_session(read(EA2C), "ea2c0634-0eb0-4923-94be-78a3e4236710.jsonl")
    artifacts = build_session_artifacts(parsed)
    commands = [c["command"] for c in artifacts["commands"]]
    assert "rm -f /mnt/c/dev/copilot-chat-test/hello.py" in commands
    assert any("git clone" in c for c in commands)
    for c in artifacts["commands"]:
        assert c["cwd"]
        assert c["timestamp"] is not None
        assert c["is_confirmed_type"] == 4


def test_urls_extracted_from_terminal_commands():
    parsed = parse_session(read(EA2C), "ea2c0634-0eb0-4923-94be-78a3e4236710.jsonl")
    artifacts = build_session_artifacts(parsed)
    urls = {u["url"] for u in artifacts["urls"]}
    assert "https://github.com/h4lpy/toastfix-demo.git" in urls
    matching = next(u for u in artifacts["urls"] if u["url"] == "https://github.com/h4lpy/toastfix-demo.git")
    assert matching["sources"] == ["terminal_command"]


def test_attachments_listed_with_full_text():
    parsed = parse_session(read(C0B4_WITH_FILE), "c0b4f2ea-e8d3-4d29-bf8c-25fca694f539_with_file.jsonl")
    artifacts = build_session_artifacts(parsed)
    assert len(artifacts["attachments"]) == 1
    a = artifacts["attachments"][0]
    assert a["id"] == "README.md"
    assert a["file_path"].endswith("README.md")
    assert a["content"].strip().startswith("# Experiments")
    assert a["content_length"] == len(a["content"])
    assert a["request_index"] == 2


def test_prompt_context_table_per_request():
    parsed = parse_session(read(C0B4_WITH_FILE), "c0b4f2ea-e8d3-4d29-bf8c-25fca694f539_with_file.jsonl")
    artifacts = build_session_artifacts(parsed)
    assert len(artifacts["prompt_context"]) == 3
    ctx2 = artifacts["prompt_context"][2]
    assert ctx2["request_index"] == 2
    assert ctx2["last_command"] == "mkdir datasets"
    assert ctx2["cwd"].endswith("experiments")
    assert ctx2["exit_code"] == "0"


def test_empty_session_produces_empty_artifacts_not_a_crash():
    parsed = parse_session('{"kind":0,"v":{"requests":[]}}\n', "x.jsonl")
    artifacts = build_session_artifacts(parsed)
    assert artifacts == {
        "files": [], "commands": [], "urls": [], "attachments": [], "prompt_context": [],
    }


def test_url_trailing_punctuation_is_stripped():
    from parser.artifacts import _record_url
    urls = {}
    _record_url(urls, "https://example.com/path.", "response_text", 0, 1)
    assert "https://example.com/path." not in urls
    assert "https://example.com/path" in urls
