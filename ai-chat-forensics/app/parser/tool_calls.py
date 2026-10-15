"""Joins tool-invocation response items to their round tool call and result.

Three pieces have to be stitched together per request (notes.md):
- response item `toolInvocationSerialized`: `toolId` (e.g. `copilot_readFile`),
  `toolCallId` (e.g. `call_YkS2...`, no suffix).
- `result.metadata.toolCallRounds[].toolCalls[]`: round `name` (e.g.
  `read_file` - a different string from `toolId`), `id` = `toolCallId` +
  `__vscode-<n>`, and a JSON-*string* `arguments`.
- `result.metadata.toolCallResults`: keyed by the full `__vscode-<n>` id;
  value is either a raw string, or a serialised prompt-element "node tree"
  that must be flattened to text.
"""

from __future__ import annotations

import json
from typing import Any


def join_tool_calls(request: dict) -> list[dict]:
    response_items = request.get("response") or []
    metadata = (request.get("result") or {}).get("metadata") or {}
    rounds = metadata.get("toolCallRounds") or []
    tool_call_results = metadata.get("toolCallResults") or {}

    round_calls_by_prefix: dict[str, dict] = {}
    for round_idx, round_ in enumerate(rounds):
        for tc in round_.get("toolCalls") or []:
            full_id = tc.get("id", "")
            prefix = full_id.split("__vscode-")[0]
            round_calls_by_prefix[prefix] = {
                "round_index": round_idx,
                "round_phase": round_.get("phase"),
                "round_model_id": round_.get("modelId"),
                "round_timestamp": round_.get("timestamp"),
                "full_id": full_id,
                "name": tc.get("name"),
                "arguments_raw": tc.get("arguments"),
                "arguments": _try_parse_json(tc.get("arguments")),
            }

    out = []
    for item in response_items:
        if not isinstance(item, dict) or item.get("kind") != "toolInvocationSerialized":
            continue
        tool_call_id = item.get("toolCallId")
        round_info = round_calls_by_prefix.get(tool_call_id, {})
        full_id = round_info.get("full_id")

        vscode_seed = None
        if full_id and "__vscode-" in full_id:
            try:
                vscode_seed = int(full_id.rsplit("__vscode-", 1)[1])
            except ValueError:
                vscode_seed = None

        raw_result = tool_call_results.get(full_id) if full_id else None
        tool_specific = item.get("toolSpecificData") or {}
        is_terminal = tool_specific.get("kind") == "terminal"

        out.append({
            "tool_call_id": tool_call_id,
            "tool_id": item.get("toolId"),
            "round_name": round_info.get("name"),
            "arguments": round_info.get("arguments"),
            "arguments_raw": round_info.get("arguments_raw"),
            "round_index": round_info.get("round_index"),
            "round_phase": round_info.get("round_phase"),
            "vscode_seed": vscode_seed,
            "is_confirmed_type": (item.get("isConfirmed") or {}).get("type"),
            "is_complete": item.get("isComplete"),
            "source": item.get("source"),
            "invocation_message": _strip_value(item.get("invocationMessage")),
            "past_tense_message": _strip_value(item.get("pastTenseMessage")),
            "is_terminal": is_terminal,
            "terminal": _extract_terminal(tool_specific) if is_terminal else None,
            "result": flatten_tool_result(raw_result),
            "raw": item,
        })
    return out


def flatten_tool_result(entry: Any) -> dict:
    """entry = toolCallResults[<full_id>]: typically {"$mid":20,"content":[{"value":...}]}."""
    if entry is None:
        return {"kind": "missing", "text": None, "raw": entry}
    if isinstance(entry, str):
        return {"kind": "string", "text": entry, "raw": entry}
    if not isinstance(entry, dict):
        return {"kind": "unknown", "text": None, "raw": entry}

    content = entry.get("content")
    if not isinstance(content, list):
        return {"kind": "unknown", "text": None, "raw": entry}

    texts: list[str] = []
    kinds: set[str] = set()
    for item in content:
        if not isinstance(item, dict):
            continue
        value = item.get("value")
        if isinstance(value, str):
            texts.append(value)
            kinds.add("string")
        elif isinstance(value, dict) and "node" in value:
            texts.append(_flatten_node(value["node"]))
            kinds.add("node_tree")
        else:
            kinds.add("unknown")

    kind = kinds.pop() if len(kinds) == 1 else ("mixed" if kinds else "unknown")
    return {"kind": kind, "text": "".join(texts) if texts else None, "raw": entry}


def _flatten_node(node: Any) -> str:
    """Walk a serialised prompt-element tree: type:2 leaves carry `text`
    (prefixed with a newline when `lineBreakBefore` is set), type:1 nodes are
    pure containers whose own text comes only from their `children`."""
    if not isinstance(node, dict):
        return ""
    if node.get("type") == 2:
        text = node.get("text", "") or ""
        return ("\n" + text) if node.get("lineBreakBefore") else text
    return "".join(_flatten_node(child) for child in (node.get("children") or []))


def _strip_value(x: Any) -> Any:
    if isinstance(x, dict) and "value" in x:
        return x["value"]
    return x


def _extract_terminal(tool_specific: dict) -> dict:
    command_line = tool_specific.get("commandLine") or {}
    confirmation = tool_specific.get("confirmation") or {}
    cwd = tool_specific.get("cwd") or {}
    terminal_state = tool_specific.get("terminalCommandState") or {}
    return {
        "command_original": command_line.get("original"),
        "command_for_display": command_line.get("forDisplay"),
        "confirmation_command_line": confirmation.get("commandLine"),
        "cwd": cwd.get("fsPath") or cwd.get("path"),
        "is_background": tool_specific.get("isBackground"),
        "language": tool_specific.get("language"),
        "command_timestamp": terminal_state.get("timestamp"),
        "raw": tool_specific,
    }


def _try_parse_json(s: Any) -> Any:
    if not isinstance(s, str):
        return None
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        return None
