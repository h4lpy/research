"""View-model helpers for templates: grouping/formatting only, no forensic
interpretation - anything that decides what a field *means* belongs in
parser/, not here."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import unquote, urlparse

import bleach
import markdown as md
from markupsafe import Markup, escape

from parser.detections import KNOWN_RESPONSE_ITEM_KINDS

_ALLOWED_TAGS = [
    "p", "br", "strong", "em", "code", "pre", "blockquote", "ul", "ol", "li",
    "h1", "h2", "h3", "h4", "h5", "h6", "a", "hr", "table", "thead", "tbody",
    "tr", "th", "td", "span", "del",
]
_ALLOWED_ATTRS = {"a": ["href", "title"], "span": ["class"], "code": ["class"]}


def render_markdown_safe(text: str | None) -> str:
    """Markdown -> HTML, then stripped to an allowlist - the model's own
    output is treated as untrusted content, same as any other evidence."""
    if not text:
        return ""
    html = md.markdown(text, extensions=["fenced_code", "tables"])
    return bleach.clean(html, tags=_ALLOWED_TAGS, attributes=_ALLOWED_ATTRS, strip=True)


_EMPTY_MD_LINK_RE = re.compile(r"\[\]\(([^)]+)\)")


def _humanize_tool_message(text: str | None) -> Markup:
    """VS Code's invocationMessage/pastTenseMessage uses an empty-text
    markdown link for the file - "Creating [](file:///c%3A/.../hello.py)" -
    which rendered as plain text shows raw link syntax. Swap each one for
    just the path's basename (plus a line-range fragment if present)."""
    if not text:
        return Markup("")

    def repl(m: re.Match) -> str:
        parsed = urlparse(m.group(1))
        path = unquote(parsed.path) or m.group(1)
        label = path.rsplit("/", 1)[-1] or path
        if parsed.fragment:
            label += f" ({parsed.fragment})"
        return f"<code>{escape(label)}</code>"

    return Markup(_EMPTY_MD_LINK_RE.sub(repl, str(escape(text))))


def format_timestamp_ms(ms: int | None) -> str:
    if ms is None:
        return "unknown time"
    dt = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M:%S.") + f"{ms % 1000:03d}Z"


def format_time_short(ms: int | None) -> str:
    """HH:MM:SS UTC for inline display next to a message - the full
    millisecond-precision timestamp stays available via the element's
    title/hover, this is just the at-a-glance version."""
    if ms is None:
        return "unknown time"
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%H:%M:%S") + " UTC"


def format_datetime_short(ms: int | None) -> str:
    """YYYY-MM-DD HH:MM UTC - compact enough for a sidebar line, still a
    full absolute UTC timestamp (full ms precision stays available via the
    element's title/hover elsewhere)."""
    if ms is None:
        return "unknown time"
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M") + " UTC"


def format_duration_ms(ms: int) -> str:
    if ms < 1000:
        return f"{ms} ms"
    seconds = ms / 1000
    if seconds < 60:
        return f"{seconds:.1f} s"
    minutes = seconds / 60
    if minutes < 60:
        return f"{minutes:.0f} min"
    return f"{minutes / 60:.1f} h"


# Documented (notes.md) but purely administrative response item kinds - IDE
# housekeeping with no conversational or forensic-action content of their
# own. Suppressed from the Chat view only: the parser still keeps every one
# of these in `response_items`/`raw`, nothing is dropped from the data - the
# Chat tab is just choosing not to clutter the transcript with them. They
# remain fully visible in the Operations/Evidence tabs (not built yet).
_ADMINISTRATIVE_KINDS = {
    "mcpServersStarting", "autoModeResolution", "undoStop",
    "progressTaskSerialized", "codeblockUri", "textEditGroup",
}

# toolId -> a small icon for the compact one-line action it produced.
# Unrecognised tool ids fall back to a generic icon, never dropped.
_TOOL_ICONS = {
    "copilot_createFile": "file",
    "copilot_createDirectory": "dir",
    "copilot_replaceString": "edit",
    "copilot_readFile": "read",
    "run_in_terminal": "exec",
}

# toolId -> what that tag means, for a hover tooltip on the tag itself.
_TOOL_DESCRIPTIONS = {
    "copilot_createFile": "Tool call: created a new file (copilot_createFile).",
    "copilot_createDirectory": "Tool call: created a new directory (copilot_createDirectory).",
    "copilot_replaceString": "Tool call: edited an existing file (copilot_replaceString).",
    "copilot_readFile": "Tool call: read a file's contents (copilot_readFile).",
    "run_in_terminal": "Tool call: ran a terminal command (run_in_terminal) - needs user approval (isConfirmed.type 4).",
}
_UNKNOWN_TOOL_DESCRIPTION = "Tool call: unrecognised tool id - see details below for the raw call."


def build_response_timeline(request_facts: dict[str, Any]) -> list[dict[str, Any]]:
    """Groups a request's raw response_items into a display-friendly
    sequence that reads like the actual chat: consecutive bare markdown
    chunks (and inline file references within them) merged into one
    rendered block, tool invocations shown as one compact action line
    (full arguments/result/confirm-type available on hover/expand, not
    inline), purely administrative kinds left out of the transcript, and
    any genuinely unrecognised kind still shown (minimally) rather than
    silently dropped."""
    tool_calls_by_id = {tc["tool_call_id"]: tc for tc in request_facts.get("tool_calls", [])}
    items = request_facts.get("response_items") or []

    timeline: list[dict[str, Any]] = []
    pending_markdown: list[str] = []

    def flush_markdown() -> None:
        if pending_markdown:
            timeline.append({
                "type": "markdown",
                "html": render_markdown_safe("".join(pending_markdown)),
            })
            pending_markdown.clear()

    for item in items:
        if not isinstance(item, dict):
            continue
        kind = item.get("kind")

        if kind is None and isinstance(item.get("value"), str):
            pending_markdown.append(item["value"])
            continue

        if kind == "inlineReference":
            # an inline file mention inside the surrounding sentence (e.g.
            # "...created [hello.py]") - keep it inline, not a separate block
            name = item.get("name")
            if name:
                pending_markdown.append(f"`{name}`")
            continue

        if kind in _ADMINISTRATIVE_KINDS:
            continue

        flush_markdown()

        if kind == "toolInvocationSerialized":
            call = tool_calls_by_id.get(item.get("toolCallId"))
            display_call = None
            if call:
                display_call = dict(call)
                display_call["invocation_message"] = _humanize_tool_message(call.get("invocation_message"))
                display_call["past_tense_message"] = _humanize_tool_message(call.get("past_tense_message"))
            tool_id = (call or {}).get("tool_id")
            timeline.append({
                "type": "tool_call",
                "call": display_call,
                "icon": _TOOL_ICONS.get(tool_id, "tool"),
                "icon_title": _TOOL_DESCRIPTIONS.get(tool_id, _UNKNOWN_TOOL_DESCRIPTION),
                "raw": item,
            })
        else:
            timeline.append({
                "type": "generic",
                "kind": kind,
                "raw": item,
                "known_kind": kind in KNOWN_RESPONSE_ITEM_KINDS,
            })

    flush_markdown()
    return timeline


_FILE_WRITE_TOOLS = {"copilot_createFile", "copilot_createDirectory", "copilot_replaceString"}
_FILE_READ_TOOLS = {"copilot_readFile"}


def _request_op_flags(req: dict[str, Any]) -> dict[str, bool]:
    """Which operation categories this request's tool calls fall into -
    feeds the Chat view's filter chips (file writes/reads, terminal,
    attachments, incomplete). Pure categorisation of already-known fields,
    not a new interpretation of what any of them mean."""
    tool_calls = req.get("tool_calls") or []
    return {
        "file-write": any(tc.get("tool_id") in _FILE_WRITE_TOOLS for tc in tool_calls),
        "file-read": any(tc.get("tool_id") in _FILE_READ_TOOLS for tc in tool_calls),
        "exec": any(tc.get("is_terminal") for tc in tool_calls),
        "attachment": bool(req.get("variables")),
        "incomplete": bool(req.get("is_incomplete")),
    }


def build_session_view(parsed: dict[str, Any]) -> list[dict[str, Any]]:
    """One row per request: the request itself, its grouped response
    timeline, and a human-readable idle-gap label if there was a
    meaningful gap since the previous request completed."""
    rows: list[dict[str, Any]] = []
    prev_end: int | None = None
    for req in parsed["requests"]:
        gap_label = None
        timestamp = req.get("timestamp")
        if prev_end is not None and timestamp is not None and timestamp > prev_end:
            gap_label = f"{format_duration_ms(timestamp - prev_end)} idle"
        rows.append({
            "request": req,
            "timeline": build_response_timeline(req),
            "gap_before": gap_label,
            "display_model": _best_known_model(req),
            "op_flags": _request_op_flags(req),
        })
        prev_end = req.get("completed_at") or timestamp
    return rows


def _best_known_model(r: dict[str, Any]) -> str | None:
    """resolved_model (result.metadata, final) is best; for a request still
    in flight (no result yet) autoModeResolution already names the real
    model, which is still better than falling back to the `auto` placeholder."""
    return (
        r.get("resolved_model")
        or (r.get("auto_mode_resolution") or {}).get("resolvedModel")
        or r.get("model_id")
    )


def build_header_summary(parsed: dict[str, Any]) -> dict[str, Any]:
    requests = parsed["requests"]
    timestamps = [r["timestamp"] for r in requests if r.get("timestamp") is not None]

    models = sorted({
        _best_known_model(r) for r in requests if _best_known_model(r)
    })
    extension_versions = sorted({
        r.get("extension_version") for r in requests if r.get("extension_version")
    })
    modes = sorted({r.get("mode_kind") for r in requests if r.get("mode_kind")})

    workspace_paths: set[str] = set()
    for r in requests:
        for item in r.get("response_items") or []:
            if not isinstance(item, dict):
                continue
            base_uri = item.get("baseUri")
            if isinstance(base_uri, dict) and base_uri.get("path"):
                workspace_paths.add(base_uri["path"])

    return {
        "models": models,
        "extension_versions": extension_versions,
        "modes": modes,
        "total_prompt_tokens": sum(r.get("prompt_tokens") or 0 for r in requests),
        "total_completion_tokens": sum(r.get("completion_tokens") or 0 for r in requests),
        "total_credits": sum(r.get("copilot_credits") or 0 for r in requests),
        "workspace_paths": sorted(workspace_paths),
        "first_prompt_time": min(timestamps) if timestamps else None,
        "last_prompt_time": max(timestamps) if timestamps else None,
        "span_label": (
            format_duration_ms(max(timestamps) - min(timestamps))
            if len(timestamps) >= 2 else None
        ),
        "filename_mismatch": any(
            w["type"] == "filename_session_id_mismatch" for w in parsed["warnings"]
        ),
    }
