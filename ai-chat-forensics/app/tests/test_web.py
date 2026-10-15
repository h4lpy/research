import io

from web.app import create_app

from .fixtures import EA2C, EEBA, read


def _post_file(client, path, filename):
    data = {
        "session_file": (io.BytesIO(read(path).encode("utf-8")), filename),
    }
    return client.post("/", data=data, content_type="multipart/form-data")


def _post_files(client, items):
    """items: list of (path, filename) tuples, uploaded together as one request."""
    data = {
        "session_file": [(io.BytesIO(read(path).encode("utf-8")), filename) for path, filename in items]
    }
    return client.post("/", data=data, content_type="multipart/form-data")


def test_upload_page_loads():
    client = create_app().test_client()
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Drag and drop" in resp.data
    assert b"F.A.I.T.H" in resp.data


def test_header_has_a_brand_icon_on_every_page():
    client = create_app().test_client()
    upload_body = client.get("/").data.decode("utf-8")
    assert 'class="brand-icon"' in upload_body
    assert "<svg" in upload_body

    session_body = _post_file(client, EEBA, "eeba4cf4-74fa-417e-86ba-bf4990fe4c03.jsonl").data.decode("utf-8")
    assert 'class="brand-icon"' in session_body


def test_redact_toggle_present_on_every_page():
    client = create_app().test_client()
    upload_body = client.get("/").data.decode("utf-8")
    assert 'id="redact-toggle"' in upload_body
    assert "redact.js" in upload_body

    session_body = _post_file(client, EEBA, "eeba4cf4-74fa-417e-86ba-bf4990fe4c03.jsonl").data.decode("utf-8")
    assert 'id="redact-toggle"' in session_body
    assert "redact.js" in session_body


def test_no_file_shows_error_not_a_crash():
    client = create_app().test_client()
    resp = client.post("/", data={}, content_type="multipart/form-data")
    assert resp.status_code == 200
    assert b"Choose a" in resp.data


def test_parsing_a_real_session_renders_expected_content():
    client = create_app().test_client()
    resp = _post_file(client, EEBA, "eeba4cf4-74fa-417e-86ba-bf4990fe4c03.jsonl")
    assert resp.status_code == 200
    body = resp.data.decode("utf-8")
    assert "h4lpy" in body
    assert "Chat initialization test" in body
    assert "Incomplete" in body
    assert "filename mismatch" not in body  # filename matches sessionId for this fixture


def test_tool_calls_and_terminal_cards_render():
    client = create_app().test_client()
    resp = _post_file(client, EA2C, "ea2c0634-0eb0-4923-94be-78a3e4236710.jsonl")
    assert resp.status_code == 200
    body = resp.data.decode("utf-8")
    assert "copilot_createFile" in body
    assert "run_in_terminal" in body
    assert "warning" in body.lower() or "note" in body.lower()


def test_model_response_markdown_is_rendered_not_raw():
    client = create_app().test_client()
    resp = _post_file(client, EEBA, "eeba4cf4-74fa-417e-86ba-bf4990fe4c03.jsonl")
    body = resp.data.decode("utf-8")
    # the markdown pipeline must not pass through raw <script> etc.
    assert "<script>alert" not in body


def test_administrative_response_kinds_are_not_shown_in_chat():
    """mcpServersStarting/autoModeResolution are IDE housekeeping, not part
    of the actual conversation - the Chat view must not clutter the
    transcript with them. The parser still keeps them in the raw data
    (see test_detections / test_full_session), only the Chat view hides
    them."""
    client = create_app().test_client()
    resp = _post_file(client, EEBA, "eeba4cf4-74fa-417e-86ba-bf4990fe4c03.jsonl")
    body = resp.data.decode("utf-8")
    assert "mcpServersStarting" not in body
    assert "autoModeResolution" not in body


def test_genuinely_unknown_response_kind_still_shown_not_dropped():
    client = create_app().test_client()
    text = (
        '{"kind":0,"v":{"requests":[{"requestId":"a","timestamp":1,'
        '"response":[{"kind":"somethingNew","data":1}]}]}}\n'
    )
    data = {"session_file": (io.BytesIO(text.encode("utf-8")), "x.jsonl")}
    resp = client.post("/", data=data, content_type="multipart/form-data")
    body = resp.data.decode("utf-8")
    assert "somethingNew" in body
    assert "meaning unknown" in body


def test_incomplete_request_header_uses_auto_mode_resolution_not_placeholder():
    """eeba4cf4's only request has no result.metadata.resolvedModel yet (it's
    incomplete), but autoModeResolution already names the real model -
    the header must not fall back to the `copilot/auto` placeholder when
    a better answer is already known."""
    client = create_app().test_client()
    resp = _post_file(client, EEBA, "eeba4cf4-74fa-417e-86ba-bf4990fe4c03.jsonl")
    body = resp.data.decode("utf-8")
    assert "mai-code-1.1-flash" in body


def test_old_footer_chip_row_is_gone():
    client = create_app().test_client()
    resp = _post_file(client, EEBA, "eeba4cf4-74fa-417e-86ba-bf4990fe4c03.jsonl")
    body = resp.data.decode("utf-8")
    assert "footer-chips" not in body


def test_message_meta_is_plain_text_full_timestamp_model_duration_no_source_lines():
    """The per-message info used to be a chip row (removed), then a
    hover-only popover with source line numbers (also removed, not useful
    and the hover wasn't trusted) - now it's always-visible plain text:
    full timestamp, model, and duration. No "L1, L2" source line numbers."""
    client = create_app().test_client()
    resp = _post_file(client, EA2C, "ea2c0634-0eb0-4923-94be-78a3e4236710.jsonl")
    body = resp.data.decode("utf-8")
    assert "msg-meta" in body
    assert "2026-10-14 08:02:42" in body  # full timestamp, not just HH:MM:SS
    assert "mai-code-1.1-flash" in body
    assert "16.1 s" in body  # elapsedMs formatted as duration
    assert ">L1<" not in body and "source:" not in body


def test_no_tagline_in_header():
    client = create_app().test_client()
    resp = client.get("/")
    assert b"nothing leaves this machine" not in resp.data


def test_avatars_present_for_both_sides():
    client = create_app().test_client()
    resp = _post_file(client, EEBA, "eeba4cf4-74fa-417e-86ba-bf4990fe4c03.jsonl")
    body = resp.data.decode("utf-8")
    assert "user-avatar" in body
    assert "ai-avatar" in body


def test_token_and_credit_info_removed_from_top_summary():
    """Still fine in the collapsed Evidence details (an investigator who
    wants it can open that), just not in the always-visible stat line."""
    client = create_app().test_client()
    resp = _post_file(client, EEBA, "eeba4cf4-74fa-417e-86ba-bf4990fe4c03.jsonl")
    body = resp.data.decode("utf-8")
    stat_line = body.split('<p class="stat-line">')[1].split("</p>")[0]
    assert "token" not in stat_line.lower()
    assert "credit" not in stat_line.lower()
    assert "Tokens / credits" in body  # still present in Evidence details


def test_no_emoji_icons_anywhere():
    """Avatars and tool-action icons are plain text tags, not emoji."""
    client = create_app().test_client()
    resp = _post_file(client, EA2C, "ea2c0634-0eb0-4923-94be-78a3e4236710.jsonl")
    body = resp.data.decode("utf-8")
    for glyph in ("👤", "🤖", "📄", "📁", "✏️", "📖", "⚡", "🔧"):
        assert glyph not in body


def test_inline_reference_stays_inline_in_the_markdown():
    """A response like "...script at [hello.py]..." must not have the
    [hello.py] inlineReference break out into its own block - it belongs
    in the sentence."""
    client = create_app().test_client()
    resp = _post_file(client, EA2C, "ea2c0634-0eb0-4923-94be-78a3e4236710.jsonl")
    body = resp.data.decode("utf-8")
    assert "<code>hello.py</code>" in body
    assert "inlineReference" not in body


def test_tool_message_empty_markdown_links_are_humanized():
    """VS Code writes tool messages like "Created [](file:///.../hello.py)"
    - raw markdown link syntax with no link text is ugly shown as plain
    text; it must come out as just the filename, not the bracket/paren
    syntax or the raw file:// URL."""
    client = create_app().test_client()
    resp = _post_file(client, EA2C, "ea2c0634-0eb0-4923-94be-78a3e4236710.jsonl")
    body = resp.data.decode("utf-8")
    assert "<code>hello.py</code>" in body
    assert "[](file" not in body
    assert "file:///c%3A" not in body


def test_multiple_files_produce_a_sidebar_entry_and_panel_for_each():
    client = create_app().test_client()
    resp = _post_files(client, [
        (EEBA, "eeba4cf4-74fa-417e-86ba-bf4990fe4c03.jsonl"),
        (EA2C, "ea2c0634-0eb0-4923-94be-78a3e4236710.jsonl"),
    ])
    assert resp.status_code == 200
    body = resp.data.decode("utf-8")
    assert body.count('class="session-nav-item') == 2
    assert 'id="session-panel-0"' in body
    assert 'id="session-panel-1"' in body
    assert "Chat initialization test" in body
    assert "Hello world program in Python" in body
    # only the first panel/nav-item should start active
    assert body.count("session-nav-item active") == 1
    assert 'class="session-panel active" id="session-panel-0"' in body
    assert body.count("session-panel active") == 1


def test_single_file_upload_still_works_through_the_multi_file_field():
    client = create_app().test_client()
    resp = _post_file(client, EEBA, "eeba4cf4-74fa-417e-86ba-bf4990fe4c03.jsonl")
    assert resp.status_code == 200
    body = resp.data.decode("utf-8")
    assert body.count('class="session-nav-item') == 1


def test_one_bad_file_among_several_does_not_block_the_valid_ones():
    client = create_app().test_client()
    data = {
        "session_file": [
            (io.BytesIO(read(EEBA).encode("utf-8")), "eeba4cf4-74fa-417e-86ba-bf4990fe4c03.jsonl"),
            (io.BytesIO(b"\xff\xfe\x00\x01"), "bad.jsonl"),
        ]
    }
    resp = client.post("/", data=data, content_type="multipart/form-data")
    assert resp.status_code == 200
    body = resp.data.decode("utf-8")
    assert body.count('class="session-nav-item') == 1
    assert "not valid UTF-8" in body


def test_artifacts_tab_present_with_files_commands_and_urls():
    client = create_app().test_client()
    resp = _post_file(client, EA2C, "ea2c0634-0eb0-4923-94be-78a3e4236710.jsonl")
    body = resp.data.decode("utf-8")
    assert 'data-tab="artifacts"' in body
    assert "c:\\dev\\copilot-chat-test\\hello.py" in body
    assert "rm -f /mnt/c/dev/copilot-chat-test/hello.py" in body
    assert "https://github.com/h4lpy/toastfix-demo.git" in body
    assert "nothing here is flagged as suspicious" in body


def test_artifacts_tab_shows_attachment_full_text_and_prompt_context():
    from .fixtures import C0B4_WITH_FILE
    client = create_app().test_client()
    resp = _post_file(client, C0B4_WITH_FILE, "c0b4f2ea-e8d3-4d29-bf8c-25fca694f539_with_file.jsonl")
    body = resp.data.decode("utf-8")
    assert "attachment-detail" in body
    assert "# Experiments" in body  # full embedded README.md text
    assert "mkdir datasets" in body  # last command, from prompt context table
    assert "Terminal/editor context by request" in body


def test_artifacts_export_buttons_and_embedded_data_present():
    client = create_app().test_client()
    resp = _post_file(client, EA2C, "ea2c0634-0eb0-4923-94be-78a3e4236710.jsonl")
    body = resp.data.decode("utf-8")
    assert 'data-export="json"' in body
    assert 'data-export="csv"' in body
    assert 'class="artifacts-data"' in body
    # the embedded JSON really does contain the artifacts data (not an empty shell)
    assert '"rm -f /mnt/c/dev/copilot-chat-test/hello.py"' in body


def test_global_search_box_present_for_single_session():
    client = create_app().test_client()
    resp = _post_file(client, EEBA, "eeba4cf4-74fa-417e-86ba-bf4990fe4c03.jsonl")
    body = resp.data.decode("utf-8")
    assert 'id="global-search"' in body
    assert "Search this session..." in body


def test_global_search_box_labelled_for_multiple_sessions():
    client = create_app().test_client()
    resp = _post_files(client, [
        (EEBA, "eeba4cf4-74fa-417e-86ba-bf4990fe4c03.jsonl"),
        (EA2C, "ea2c0634-0eb0-4923-94be-78a3e4236710.jsonl"),
    ])
    body = resp.data.decode("utf-8")
    assert "Search all 2 sessions..." in body
    assert 'class="session-nav-match-badge"' in body


def test_workspace_hash_tool_linked_from_upload_and_sidebar():
    client = create_app().test_client()
    upload_body = client.get("/").data.decode("utf-8")
    assert '/tools/workspace-hash' in upload_body

    session_body = _post_file(client, EEBA, "eeba4cf4-74fa-417e-86ba-bf4990fe4c03.jsonl").data.decode("utf-8")
    assert '/tools/workspace-hash' in session_body


def test_workspace_hash_tool_get_shows_empty_form():
    client = create_app().test_client()
    resp = client.get("/tools/workspace-hash")
    assert resp.status_code == 200
    body = resp.data.decode("utf-8")
    assert "Workspace storage hash calculator" in body
    assert "Evidence:" in body
    assert "<table" not in body  # no results table until a form is submitted


def test_workspace_hash_tool_post_computes_variants():
    client = create_app().test_client()
    resp = client.post("/tools/workspace-hash", data={
        "path": "C:\\dev\\research",
        "os_type": "windows",
        "ctime_ms": "1792008626997",
        "inode": "",
    })
    assert resp.status_code == 200
    body = resp.data.decode("utf-8")
    assert "<table" in body
    assert "c:\\dev\\research1792008626997" in body


def test_workspace_hash_tool_bad_ctime_does_not_crash():
    client = create_app().test_client()
    resp = client.post("/tools/workspace-hash", data={
        "path": "C:\\dev\\research",
        "os_type": "windows",
        "ctime_ms": "not a number",
        "inode": "",
    })
    assert resp.status_code == 200
    body = resp.data.decode("utf-8")
    assert "<table" in body  # falls back to path-only, still renders


def test_workspace_hash_tool_empty_path_shows_no_results():
    client = create_app().test_client()
    resp = client.post("/tools/workspace-hash", data={"path": "", "os_type": "windows"})
    assert resp.status_code == 200
    assert "<table" not in resp.data.decode("utf-8")


def test_exchange_ids_are_panel_scoped_not_just_request_scoped():
    """Regression: with multiple sessions loaded, every session's request 0
    used to share the plain id="request-0", so anchor links only ever
    jumped to the first one in the DOM. IDs must be namespaced by panel."""
    client = create_app().test_client()
    resp = _post_files(client, [
        (EEBA, "eeba4cf4-74fa-417e-86ba-bf4990fe4c03.jsonl"),
        (EA2C, "ea2c0634-0eb0-4923-94be-78a3e4236710.jsonl"),
    ])
    body = resp.data.decode("utf-8")
    assert 'id="request-0-0"' in body  # first session's request 0
    assert 'id="request-1-0"' in body  # second session's request 0
    assert body.count('id="request-0-0"') == 1
    assert body.count('id="request-1-0"') == 1


def test_artifacts_links_use_panel_scoped_ids_matching_exchanges():
    client = create_app().test_client()
    resp = _post_file(client, EA2C, "ea2c0634-0eb0-4923-94be-78a3e4236710.jsonl")
    body = resp.data.decode("utf-8")
    # the file was created in request 0 - the Artifacts files table must
    # link to the same id the Chat exchange actually has
    assert 'href="#request-0-0"' in body
    assert 'id="request-0-0"' in body


def test_filter_chips_present_with_expected_categories():
    client = create_app().test_client()
    resp = _post_file(client, EA2C, "ea2c0634-0eb0-4923-94be-78a3e4236710.jsonl")
    body = resp.data.decode("utf-8")
    for f in ("file-write", "file-read", "exec", "attachment", "incomplete", "bookmarked"):
        assert f'data-filter="{f}"' in body


def test_flag_toggle_present_per_exchange():
    client = create_app().test_client()
    resp = _post_file(client, EEBA, "eeba4cf4-74fa-417e-86ba-bf4990fe4c03.jsonl")
    body = resp.data.decode("utf-8")
    assert body.count('class="flag-toggle"') == 1  # eeba4cf4 has exactly one request


def test_flag_toggle_is_an_svg_icon_not_text():
    """The toggle must not render literal 'Flag' text - it's an icon."""
    client = create_app().test_client()
    resp = _post_file(client, EEBA, "eeba4cf4-74fa-417e-86ba-bf4990fe4c03.jsonl")
    body = resp.data.decode("utf-8")
    assert 'class="flag-icon"' in body
    assert "<svg" in body
    # the button's own visible text content must be empty (icon only);
    # isolate the button tag itself, not the rest of the page
    import re
    m = re.search(r'<button type="button" class="flag-toggle"[^>]*>(.*?)</button>', body, re.DOTALL)
    assert m, "flag-toggle button not found"
    inner_text = re.sub(r"<[^>]+>", "", m.group(1)).strip()
    assert inner_text == ""


def test_sidebar_shows_session_start_time():
    client = create_app().test_client()
    resp = _post_file(client, EEBA, "eeba4cf4-74fa-417e-86ba-bf4990fe4c03.jsonl")
    body = resp.data.decode("utf-8")
    assert 'class="session-nav-time"' in body
    # eeba4cf4's creationDate is 2026-10-15 08:09:29.129 UTC
    assert "2026-10-15 08:09" in body


def test_sidebar_widened_for_the_extra_line():
    import pathlib
    css_path = pathlib.Path(__file__).resolve().parents[1] / "web" / "static" / "style.css"
    body = css_path.read_text(encoding="utf-8")
    assert "flex: 0 0 290px;" in body


def test_filter_chips_and_action_tags_have_hover_descriptions():
    client = create_app().test_client()
    resp = _post_file(client, EA2C, "ea2c0634-0eb0-4923-94be-78a3e4236710.jsonl")
    body = resp.data.decode("utf-8")
    # filter chips in the sidebar
    assert 'data-filter="exec" title="Exchanges where the AI ran a terminal command' in body
    assert 'data-filter="file-write" title="Exchanges where the AI created' in body
    # the same categories, explained where they appear inline in the message
    assert 'class="action-icon" title="Tool call: created a new file' in body
    assert 'class="action-icon" title="Tool call: ran a terminal command' in body


def test_op_flags_reflect_what_each_request_actually_did():
    import re
    client = create_app().test_client()
    resp = _post_file(client, EA2C, "ea2c0634-0eb0-4923-94be-78a3e4236710.jsonl")
    body = resp.data.decode("utf-8")

    def article_tag(panel_idx, req_idx):
        m = re.search(
            r'<article class="exchange"[^>]*id="request-%d-%d"[^>]*>' % (panel_idx, req_idx),
            body,
        )
        assert m, f"no <article> found for request-{panel_idx}-{req_idx}"
        return m.group(0)

    # request 0 creates hello.py - a file write, not exec/read/incomplete
    tag0 = article_tag(0, 0)
    assert 'data-op-file-write="1"' in tag0
    assert 'data-op-exec="0"' in tag0
    assert 'data-op-incomplete="0"' in tag0

    # request 5 runs "rm -f ..." via the terminal - exec, not a file write
    tag5 = article_tag(0, 5)
    assert 'data-op-exec="1"' in tag5
    assert 'data-op-file-write="0"' in tag5


def test_non_utf8_upload_shows_error_not_a_500():
    client = create_app().test_client()
    data = {"session_file": (io.BytesIO(b"\xff\xfe\x00\x01"), "bad.jsonl")}
    resp = client.post("/", data=data, content_type="multipart/form-data")
    assert resp.status_code == 200
    assert b"not valid UTF-8" in resp.data
