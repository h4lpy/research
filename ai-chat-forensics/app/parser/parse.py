"""Public entry point: parse_session(text, filename) -> plain JSON-serialisable dict.

Pure Python, no Flask/DOM/filesystem imports - takes file text in, returns
data out, so it can be reused from the web app, a CLI, or tests unchanged.
"""

from __future__ import annotations

from typing import Any

from . import derive, detections, mutation_log, rendered_message
from . import tool_calls as tool_calls_mod
from .hash import sha256_hex


def parse_session(text: str, filename: str) -> dict[str, Any]:
    replay_result = mutation_log.replay(text)
    state = replay_result["state"]
    ops = replay_result["ops"]
    warnings = list(replay_result["warnings"])
    provenance = replay_result["provenance"]

    warnings += detections.run_all(
        filename, state, ops, replay_result["initial_requests_count"]
    )

    initial_requests_count = replay_result["initial_requests_count"]
    requests_out = []
    for idx, req in enumerate(state.get("requests") or []):
        if not isinstance(req, dict):
            continue
        requests_out.append(_build_request(idx, req, ops, initial_requests_count))

    file_bytes = text.encode("utf-8")

    return {
        "file": {
            "name": filename,
            "size": len(file_bytes),
            "sha256": sha256_hex(file_bytes),
            "line_count": len(text.split("\n")),
        },
        "session": derive.derive_session_facts(state),
        "requests": requests_out,
        "ops": ops,
        "warnings": warnings,
        "provenance": provenance,
    }


def _build_request(
    idx: int, req: dict[str, Any], ops: list[dict], initial_requests_count: int | None
) -> dict[str, Any]:
    metadata = ((req.get("result") or {}).get("metadata")) or {}
    response_items = req.get("response") or []

    markdown_text = "".join(
        item.get("value", "")
        for item in response_items
        if isinstance(item, dict) and "kind" not in item and isinstance(item.get("value"), str)
    )

    return {
        "index": idx,
        **derive.derive_request_facts(req),
        "tool_calls": tool_calls_mod.join_tool_calls(req),
        "rendered_user_message": rendered_message.parse_rendered_message(
            metadata.get("renderedUserMessage")
        ),
        "rendered_global_context": rendered_message.parse_rendered_message(
            metadata.get("renderedGlobalContext")
        ),
        "response_markdown": markdown_text,
        "response_items": response_items,
        "source_lines": mutation_log.request_source_lines(ops, idx, initial_requests_count),
        "raw": req,
    }
