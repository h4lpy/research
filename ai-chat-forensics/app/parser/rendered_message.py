"""Parses `result.metadata.renderedUserMessage` / `renderedGlobalContext`.

These are arrays of `{"type":1,"text":...}` (actual prompt text, as sent to
the model) and `{"type":3,"cacheType":"ephemeral"}` (prompt-cache markers,
not content - notes.md). The text itself is a flat document with known
XML-like section tags; unknown tags/leftover text are kept verbatim rather
than dropped, per the version-tolerance rule in CLAUDE.md.
"""

from __future__ import annotations

import re
from typing import Any

_CONTEXT_TAGS = [
    "context", "editorContext", "attachments", "reminderInstructions", "userRequest",
]
_GLOBAL_TAGS = [
    "environment_info", "workspace_info", "userMemory", "sessionMemory", "repoMemory",
]
_ALL_TAGS = _CONTEXT_TAGS + _GLOBAL_TAGS

_ATTACHMENT_RE = re.compile(
    r'<attachment id="(?P<id>[^"]*)" filePath="(?P<file_path>[^"]*)">(?P<content>.*?)</attachment>',
    re.DOTALL,
)
_LAST_COMMAND_RE = re.compile(r"^Last Command:\s*(.*)$", re.MULTILINE)
_CWD_RE = re.compile(r"^Cwd:\s*(.*)$", re.MULTILINE)
_EXIT_CODE_RE = re.compile(r"^Exit Code:\s*(.*)$", re.MULTILINE)
_CURRENT_DATE_RE = re.compile(r"The current date is\s*(.*?)\.", re.MULTILINE)
_TERMINAL_RE = re.compile(r"^Terminal:\s*(.*)$", re.MULTILINE)


def parse_rendered_message(entries: Any) -> dict:
    """entries: the raw renderedUserMessage/renderedGlobalContext array (or None)."""
    if not isinstance(entries, list):
        return {"raw_text": None, "cache_markers": [], "sections": {}, "unparsed": None}

    text_parts: list[str] = []
    cache_markers: list[dict] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if entry.get("type") == 1 and isinstance(entry.get("text"), str):
            text_parts.append(entry["text"])
        elif entry.get("type") == 3:
            cache_markers.append({k: v for k, v in entry.items() if k != "type"})
        else:
            # unknown entry shape: keep it visible rather than silently dropping it
            cache_markers.append({"unknown_entry": entry})

    raw_text = "".join(text_parts)
    sections: dict[str, Any] = {}
    consumed_spans: list[tuple[int, int]] = []

    for tag in _ALL_TAGS:
        pattern = re.compile(rf"<{tag}>(.*?)</{tag}>", re.DOTALL)
        m = pattern.search(raw_text)
        if not m:
            continue
        consumed_spans.append(m.span())
        inner = m.group(1)
        key = _tag_to_key(tag)
        if tag == "context":
            sections[key] = _parse_context(inner)
        elif tag == "attachments":
            sections[key] = _parse_attachments(inner)
        else:
            sections[key] = inner.strip("\n")

    unparsed = _remove_spans(raw_text, consumed_spans).strip()

    return {
        "raw_text": raw_text,
        "cache_markers": cache_markers,
        "sections": sections,
        "unparsed": unparsed or None,
    }


def _tag_to_key(tag: str) -> str:
    # editorContext -> editor_context, environment_info -> environment_info (already snake)
    return re.sub(r"(?<!^)(?=[A-Z])", "_", tag).lower()


def _parse_context(inner: str) -> dict:
    date_m = _CURRENT_DATE_RE.search(inner)
    last_command_m = _LAST_COMMAND_RE.search(inner)
    cwd_m = _CWD_RE.search(inner)
    exit_code_m = _EXIT_CODE_RE.search(inner)
    return {
        "raw": inner.strip("\n"),
        "current_date": date_m.group(1).strip() if date_m else None,
        "terminals": [m.group(1).strip() for m in _TERMINAL_RE.finditer(inner)],
        "last_command": last_command_m.group(1).strip() if last_command_m else None,
        "cwd": cwd_m.group(1).strip() if cwd_m else None,
        "exit_code": exit_code_m.group(1).strip() if exit_code_m else None,
    }


def _parse_attachments(inner: str) -> list[dict]:
    return [
        {"id": m.group("id"), "file_path": m.group("file_path"), "content": m.group("content")}
        for m in _ATTACHMENT_RE.finditer(inner)
    ]


def _remove_spans(text: str, spans: list[tuple[int, int]]) -> str:
    if not spans:
        return text
    spans = sorted(spans)
    out = []
    pos = 0
    for start, end in spans:
        out.append(text[pos:start])
        pos = end
    out.append(text[pos:])
    return "".join(out)
