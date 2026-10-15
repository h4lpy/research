"""Session-level detections: forensic notes about the replayed state.

Each detection returns plain dicts with a `type`, a human `message`, and an
`evidence` label (`observed` / `source` / `hypothesis`) matching notes.md.
These are warnings/notes, not necessarily errors - a session with zero
requests is valid, for example.
"""

from __future__ import annotations

from typing import Any

# Fields actually observed across the research datasets (notes.md "Fields seen
# in 0.60.0" plus everything seen in the 0.59.0/0.60.0 samples). Anything else
# is shown as raw data with "meaning unknown", not dropped.
KNOWN_SESSION_FIELDS = {
    "version", "creationDate", "sessionId", "initialLocation",
    "responderUsername", "hasPendingEdits", "customTitle", "requests",
    "pendingRequests", "inputState",
}

KNOWN_REQUEST_FIELDS = {
    "requestId", "timestamp", "agent", "modelId", "responseId",
    "responseTimestamp", "modelState", "contentReferences", "codeCitations",
    "timeSpentWaiting", "modeInfo", "response", "message", "variableData",
    "result", "responseMarkdownInfo", "followups", "completionTokens",
    "promptTokens", "outputBuffer", "promptTokenDetails", "copilotCredits",
    "elapsedMs", "editedFileEvents",
}

# A bare markdown chunk has no "kind" key at all (just value/supportThemeIcons/baseUri).
KNOWN_RESPONSE_ITEM_KINDS = {
    None, "inlineReference", "toolInvocationSerialized", "textEditGroup",
    "codeblockUri", "undoStop", "mcpServersStarting", "progressTaskSerialized",
    "autoModeResolution",
}

def run_all(
    filename: str,
    state: dict[str, Any],
    ops: list[dict],
    initial_requests_count: int | None,
) -> list[dict]:
    warnings: list[dict] = []
    warnings += check_filename_matches_session_id(filename, state.get("sessionId"))
    warnings += check_zero_requests(state.get("requests", []))
    warnings += check_incomplete_requests(state.get("requests", []))
    warnings += check_initial_requests_count(initial_requests_count or 0)
    warnings += check_inputstate_written_without_prompt(ops)
    warnings += check_unknown_top_level_fields(state)
    warnings += check_unknown_request_fields(state.get("requests", []))
    warnings += check_unknown_response_item_kinds(state.get("requests", []))
    warnings += check_multiple_extension_versions(state.get("requests", []))
    return warnings


def check_filename_matches_session_id(filename: str, session_id: str | None) -> list[dict]:
    if session_id is None:
        return []
    stem = filename[: -len(".jsonl")] if filename.endswith(".jsonl") else filename
    if stem != session_id:
        return [{
            "type": "filename_session_id_mismatch",
            "message": (
                f"filename stem {stem!r} does not match sessionId {session_id!r}; "
                "the file may have been renamed or copied"
            ),
            "evidence": "observed",
        }]
    return []


def check_zero_requests(requests: list) -> list[dict]:
    if not requests:
        return [{
            "type": "zero_requests",
            "message": "session has no requests; a file with only the kind:0 snapshot is normal (a session opened and never used)",
            "evidence": "observed",
        }]
    return []


def check_incomplete_requests(requests: list) -> list[dict]:
    out = []
    for idx, req in enumerate(requests):
        if req is None:
            continue
        model_state = req.get("modelState") or {}
        if model_state.get("value") == 0 and "result" not in req:
            out.append({
                "type": "incomplete_request",
                "request_index": idx,
                "requestId": req.get("requestId"),
                "message": (
                    f"request {idx} has modelState.value 0 and no result: "
                    "incomplete / in-flight, not an error. A response ending "
                    "mid-sentence is expected."
                ),
                "evidence": "observed",
            })
    return out


def check_initial_requests_count(initial_request_count: int) -> list[dict]:
    if initial_request_count > 0:
        return [{
            "type": "initial_snapshot_already_populated",
            "message": (
                f"the kind:0 snapshot (line 1) already contains {initial_request_count} "
                "request(s); either compaction happened before this file was captured, "
                "or this copy does not start at the file's true first byte. Earlier "
                "per-line history for those requests is not recoverable from this file."
            ),
            "evidence": "hypothesis",
        }]
    return []


def check_inputstate_written_without_prompt(ops: list[dict]) -> list[dict]:
    out = []
    for op in ops:
        if op["kind"] == 0:
            continue
        if op["path"][:1] == ["inputState"]:
            out.append({
                "type": "written_without_prompt",
                "line": op["line"],
                "path": op["path"],
                "message": (
                    f"line {op['line']} sets {'/'.join(map(str, op['path']))} with no "
                    "new request alongside it; opening an existing session can append "
                    "lines like this with no prompt sent. Not evidence of chat activity."
                ),
                "evidence": "observed",
            })
    return out


def check_unknown_top_level_fields(state: dict[str, Any]) -> list[dict]:
    unknown = sorted(set(state.keys()) - KNOWN_SESSION_FIELDS)
    if unknown:
        return [{
            "type": "unknown_session_fields",
            "fields": unknown,
            "message": f"unrecognised top-level session field(s): {', '.join(unknown)} (meaning unknown, shown as raw data)",
            "evidence": "hypothesis",
        }]
    return []


def check_unknown_request_fields(requests: list) -> list[dict]:
    seen_unknown: dict[str, list[int]] = {}
    for idx, req in enumerate(requests):
        if not isinstance(req, dict):
            continue
        for field in set(req.keys()) - KNOWN_REQUEST_FIELDS:
            seen_unknown.setdefault(field, []).append(idx)
    return [
        {
            "type": "unknown_request_fields",
            "field": field,
            "request_indices": indices,
            "message": f"unrecognised request field {field!r} (meaning unknown, shown as raw data)",
            "evidence": "hypothesis",
        }
        for field, indices in sorted(seen_unknown.items())
    ]


def check_unknown_response_item_kinds(requests: list) -> list[dict]:
    seen_unknown: dict[str, list[int]] = {}
    for idx, req in enumerate(requests):
        if req is None:
            continue
        for item in req.get("response") or []:
            if not isinstance(item, dict):
                continue
            kind = item.get("kind")
            if kind not in KNOWN_RESPONSE_ITEM_KINDS:
                seen_unknown.setdefault(kind, []).append(idx)
    return [
        {
            "type": "unknown_response_item_kind",
            "kind": kind,
            "request_indices": indices,
            "message": f"response item kind {kind!r} is not in the documented set (meaning unknown, shown as raw data)",
            "evidence": "hypothesis",
        }
        for kind, indices in seen_unknown.items()
    ]


def check_multiple_extension_versions(requests: list) -> list[dict]:
    versions: dict[str, list[int]] = {}
    for idx, req in enumerate(requests):
        if req is None:
            continue
        version = (req.get("agent") or {}).get("extensionVersion")
        if version:
            versions.setdefault(version, []).append(idx)
    if len(versions) > 1:
        return [{
            "type": "multiple_extension_versions",
            "versions": versions,
            "message": f"session spans multiple Copilot Chat versions: {sorted(versions)}; field shapes can differ between them",
            "evidence": "observed",
        }]
    return []


