from parser.parse import parse_session

from .fixtures import C0B4, C0B4_WITH_FILE, read


def test_append_only_first_14_lines_identical_to_base_session():
    base_lines = read(C0B4).split("\n")
    with_file_lines = read(C0B4_WITH_FILE).split("\n")
    assert with_file_lines[:14] == base_lines[:14]


def test_attachment_in_variable_data():
    text = read(C0B4_WITH_FILE)
    parsed = parse_session(text, "c0b4f2ea-e8d3-4d29-bf8c-25fca694f539_with_file.jsonl")
    assert len(parsed["requests"]) == 3

    req2 = parsed["requests"][2]
    variables = req2["variables"]
    assert len(variables) == 1
    assert variables[0]["kind"] == "file"
    assert variables[0]["name"] == "README.md"


def test_attachment_full_text_embedded_in_rendered_message():
    text = read(C0B4_WITH_FILE)
    parsed = parse_session(text, "c0b4f2ea-e8d3-4d29-bf8c-25fca694f539_with_file.jsonl")
    req2 = parsed["requests"][2]

    attachments = req2["rendered_user_message"]["sections"]["attachments"]
    assert len(attachments) == 1
    assert attachments[0]["id"] == "README.md"
    assert attachments[0]["file_path"].endswith("README.md")
    assert attachments[0]["content"].strip().startswith("# Experiments")


def test_context_section_parsed_into_known_fields():
    text = read(C0B4_WITH_FILE)
    parsed = parse_session(text, "c0b4f2ea-e8d3-4d29-bf8c-25fca694f539_with_file.jsonl")
    context = parsed["requests"][2]["rendered_user_message"]["sections"]["context"]
    assert context["last_command"] == "mkdir datasets"
    assert context["exit_code"] == "0"
    assert context["cwd"] == "C:\\dev\\research\\ai-chat-forensics\\experiments"
    assert len(context["terminals"]) == 2


def test_cache_markers_are_kept_but_not_treated_as_content():
    text = read(C0B4_WITH_FILE)
    parsed = parse_session(text, "c0b4f2ea-e8d3-4d29-bf8c-25fca694f539_with_file.jsonl")
    rendered = parsed["requests"][2]["rendered_user_message"]
    assert any(m.get("cacheType") == "ephemeral" for m in rendered["cache_markers"])
    assert "cacheType" not in rendered["raw_text"]
