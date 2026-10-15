"""Session-level artifact extraction for DFIR triage: every file touched,
every terminal command run, every URL/host referenced, every attachment fed
in (with its full embedded text, as of prompt time), and the terminal/editor
context snapshot captured at each prompt - across the whole session,
deduplicated where it makes sense, each entry pointing back to the
request(s) that produced it. Purely factual listing: this module does not
judge anything as suspicious, only extracts what happened. All of this is
built from fields the parser already resolved (tool_calls, rendered_user_message,
response_markdown); nothing here changes what those fields mean.
"""

from __future__ import annotations

import re
from typing import Any

_URL_RE = re.compile(r"https?://[^\s)\]\"'<>]+")

# toolId -> the key in its round-call arguments that names the path.
_PATH_ARG_KEYS = {
    "copilot_createFile": "filePath",
    "copilot_readFile": "filePath",
    "copilot_replaceString": "filePath",
    "copilot_createDirectory": "dirPath",
}

_ACTIONS = {
    "copilot_createFile": "created",
    "copilot_readFile": "read",
    "copilot_replaceString": "edited",
    "copilot_createDirectory": "created (directory)",
}


def build_session_artifacts(parsed: dict[str, Any]) -> dict[str, Any]:
    requests = parsed.get("requests") or []

    files: dict[str, dict[str, Any]] = {}
    commands: list[dict[str, Any]] = []
    urls: dict[str, dict[str, Any]] = {}
    attachments: list[dict[str, Any]] = []

    prompt_context: list[dict[str, Any]] = []

    for req in requests:
        idx = req.get("index")
        timestamp = req.get("timestamp")

        for a in ((req.get("rendered_user_message") or {}).get("sections") or {}).get("attachments") or []:
            content = a.get("content") or ""
            attachments.append({
                "id": a.get("id"),
                "file_path": a.get("file_path"),
                "content": content,
                "content_length": len(content),
                "request_index": idx,
                "timestamp": timestamp,
            })

        ctx = ((req.get("rendered_user_message") or {}).get("sections") or {}).get("context")
        if ctx:
            prompt_context.append({
                "request_index": idx,
                "timestamp": timestamp,
                "current_date": ctx.get("current_date"),
                "last_command": ctx.get("last_command"),
                "cwd": ctx.get("cwd"),
                "exit_code": ctx.get("exit_code"),
                "terminals": ctx.get("terminals") or [],
            })

        for call in req.get("tool_calls") or []:
            tool_id = call.get("tool_id")

            if call.get("is_terminal") and call.get("terminal"):
                terminal = call["terminal"]
                command = terminal.get("command_original") or terminal.get("command_for_display")
                if command:
                    commands.append({
                        "command": command,
                        "cwd": terminal.get("cwd"),
                        "request_index": idx,
                        "timestamp": terminal.get("command_timestamp") or timestamp,
                        "is_confirmed_type": call.get("is_confirmed_type"),
                    })
                    for url in _URL_RE.findall(command):
                        _record_url(urls, url, "terminal_command", idx, timestamp)
                continue

            path_key = _PATH_ARG_KEYS.get(tool_id)
            if path_key and isinstance(call.get("arguments"), dict):
                path = call["arguments"].get(path_key)
                if path:
                    _record_file(files, path, _ACTIONS.get(tool_id, tool_id), idx, timestamp)

        for url in _URL_RE.findall(req.get("response_markdown") or ""):
            _record_url(urls, url, "response_text", idx, timestamp)

    return {
        "files": sorted(files.values(), key=lambda f: f["path"]),
        "commands": commands,
        "urls": sorted(urls.values(), key=lambda u: u["url"]),
        "attachments": attachments,
        "prompt_context": prompt_context,
    }


def _record_file(files: dict, path: str, action: str, idx: int | None, timestamp: int | None) -> None:
    entry = files.setdefault(path, {
        "path": path,
        "actions": [],
        "request_indices": [],
        "first_seen": timestamp,
        "last_seen": timestamp,
    })
    entry["actions"].append(action)
    entry["request_indices"].append(idx)
    if timestamp is not None:
        if entry["first_seen"] is None or timestamp < entry["first_seen"]:
            entry["first_seen"] = timestamp
        if entry["last_seen"] is None or timestamp > entry["last_seen"]:
            entry["last_seen"] = timestamp


def _record_url(urls: dict, url: str, source: str, idx: int | None, timestamp: int | None) -> None:
    url = url.rstrip(".,;:!?")
    entry = urls.setdefault(url, {"url": url, "sources": [], "request_indices": []})
    entry["sources"].append(source)
    entry["request_indices"].append(idx)
