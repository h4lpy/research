"""Replay engine for the Copilot Chat session mutation log.

Each line of a `chatSessions/*.jsonl` file is one op against an in-memory
object: `kind:0` is a full snapshot, `kind:1` sets a value at a path,
`kind:2` pushes items onto an array (optionally truncating it first via
`i`), `kind:3` deletes a value at a path. Line order is write order, not
event order - see notes.md.

This module only replays; it does not interpret what the resulting state
means (that's detections.py / derive.py).
"""

from __future__ import annotations

import copy
import json
from typing import Any

TRUNCATION_MARKER_PREFIX = "[VS Code: value truncated for persistence"

# Keys whose value is an epoch-ms timestamp, wherever they appear in a pushed
# or set value (request-level, round-level, terminalCommandState, ...).
_TIMESTAMP_FIELDS = {"timestamp", "responseTimestamp", "completedAt"}


def replay(text: str, max_line: int | None = None) -> dict[str, Any]:
    """Replay a session's JSONL text.

    Returns {"state", "ops", "warnings", "provenance", "initial_requests_count"}.
    Never raises: a bad line is recorded as a warning and replay continues.
    """
    root: dict[str, Any] = {}
    ops: list[dict[str, Any]] = []
    file_warnings: list[dict[str, Any]] = []
    provenance: dict[str, list[int]] = {}
    seen_first_content_line = False
    initial_requests_count: int | None = None
    running_max_timestamp: int | None = None
    running_max_timestamp_line: int | None = None

    for line_no, raw in enumerate(text.split("\n"), start=1):
        if max_line is not None and line_no > max_line:
            break

        stripped = raw.strip()
        if not stripped:
            continue  # a blank trailing line is normal, not an error

        try:
            entry = json.loads(stripped)
        except json.JSONDecodeError as e:
            file_warnings.append(
                {"type": "invalid_json", "line": line_no, "message": str(e)}
            )
            continue

        if not isinstance(entry, dict) or "kind" not in entry:
            file_warnings.append(
                {
                    "type": "malformed_entry",
                    "line": line_no,
                    "message": "line is valid JSON but has no 'kind' field",
                }
            )
            continue

        kind = entry.get("kind")
        path = entry.get("k")
        value = entry.get("v")
        i_field = entry.get("i")

        is_first_content_line = not seen_first_content_line
        seen_first_content_line = True

        try:
            if kind == 0:
                if not is_first_content_line:
                    file_warnings.append(
                        {
                            "type": "unexpected_additional_snapshot",
                            "line": line_no,
                            "message": (
                                "A kind:0 snapshot appeared after the first content "
                                "line; replayed state has been reset to this snapshot. "
                                "Unexpected in a single untouched file."
                            ),
                            "evidence": "hypothesis",
                        }
                    )
                root = copy.deepcopy(value) if isinstance(value, dict) else {}
                provenance.setdefault("", []).append(line_no)
                ops.append(_make_op(line_no, 0, [], None, value))
                if is_first_content_line and isinstance(value, dict):
                    initial_requests_count = len(value.get("requests") or [])
            else:
                if is_first_content_line:
                    file_warnings.append(
                        {
                            "type": "missing_initial_entry",
                            "line": line_no,
                            "message": (
                                "First entry is not a kind:0 snapshot. VS Code itself "
                                "refuses to open such a file; replaying from an empty "
                                "state."
                            ),
                            "evidence": "source",
                        }
                    )
                if path is None:
                    raise ValueError(f"kind:{kind} entry has no 'k' path")

                pushed_range = None
                if kind == 1:
                    _apply_set(root, path, value)
                elif kind == 2:
                    pushed_range = _apply_push(root, path, value, i_field)
                elif kind == 3:
                    _apply_delete(root, path)
                else:
                    file_warnings.append(
                        {
                            "type": "unknown_kind",
                            "line": line_no,
                            "kind": kind,
                            "message": f"unrecognised mutation kind {kind!r}; op not applied",
                        }
                    )
                    continue

                path_key = _path_key(path)
                provenance.setdefault(path_key, []).append(line_no)
                op = _make_op(line_no, kind, path, i_field, value)
                if pushed_range is not None:
                    op["pushed_range"] = list(pushed_range)
                ops.append(op)
        except Exception as e:  # noqa: BLE001 - replay must never crash on bad input
            file_warnings.append(
                {
                    "type": "op_apply_error",
                    "line": line_no,
                    "message": f"{type(e).__name__}: {e}",
                }
            )
            continue

        for sub_path, marker_text in _find_truncation_markers(value):
            file_warnings.append(
                {
                    "type": "truncated_value",
                    "line": line_no,
                    "path": list(path or []) + list(sub_path),
                    "message": marker_text,
                    "evidence": "source",
                }
            )

        for field, ts in _find_timestamps(value, path or []):
            if running_max_timestamp is not None and ts < running_max_timestamp:
                file_warnings.append(
                    {
                        "type": "timestamp_out_of_order",
                        "line": line_no,
                        "field": field,
                        "timestamp": ts,
                        "earlier_line": running_max_timestamp_line,
                        "earlier_timestamp": running_max_timestamp,
                        "message": (
                            f"line {line_no} ({field}={ts}) is earlier than a "
                            f"timestamp already seen at line {running_max_timestamp_line} "
                            f"({running_max_timestamp}); line order is write order, not "
                            "event order - do not trust line position for chronology"
                        ),
                        "evidence": "observed",
                    }
                )
            else:
                running_max_timestamp = ts
                running_max_timestamp_line = line_no

    return {
        "state": root,
        "ops": ops,
        "warnings": file_warnings,
        "provenance": provenance,
        "initial_requests_count": initial_requests_count,
    }


def request_source_lines(
    ops: list[dict[str, Any]], index: int, initial_requests_count: int | None
) -> list[int]:
    """Line numbers that wrote or touched `requests[index]`.

    A `kind:2` push onto `["requests"]` only carries the array's path, not
    the index(es) it landed at - `pushed_range` (recorded at push time)
    is what lets this attribute that line to the right request(s). The
    kind:0 snapshot is only attributed to requests it actually contained.
    """
    lines: set[int] = set()
    for op in ops:
        if op["kind"] == 0:
            if initial_requests_count is not None and index < initial_requests_count:
                lines.add(op["line"])
            continue
        path = op["path"]
        if op["kind"] == 2 and path == ["requests"]:
            rng = op.get("pushed_range")
            if rng and rng[0] <= index < rng[1]:
                lines.add(op["line"])
        elif len(path) >= 2 and path[0] == "requests" and path[1] == index:
            lines.add(op["line"])
    return sorted(lines)


def _path_key(path: list) -> str:
    return "/".join(str(seg) for seg in path)


def _make_op(line_no: int, kind: int, path: list, i: int | None, value: Any) -> dict:
    return {"line": line_no, "kind": kind, "path": list(path), "i": i, "size": _approx_size(value)}


def _approx_size(value: Any) -> int | None:
    if value is None:
        return 0
    try:
        return len(json.dumps(value, ensure_ascii=False))
    except (TypeError, ValueError):
        return None


def _descend(node: Any, seg: Any, next_seg: Any) -> Any:
    if isinstance(node, list):
        idx = int(seg)
        while len(node) <= idx:
            node.append(None)
        if node[idx] is None:
            node[idx] = {} if isinstance(next_seg, str) else []
        return node[idx]
    if isinstance(node, dict):
        if seg not in node or node[seg] is None:
            node[seg] = {} if isinstance(next_seg, str) else []
        return node[seg]
    raise TypeError(f"cannot descend into {type(node).__name__} at segment {seg!r}")


def _parent_and_key(root: dict, path: list) -> tuple[Any, Any]:
    node = root
    for idx in range(len(path) - 1):
        node = _descend(node, path[idx], path[idx + 1])
    return node, path[-1]


def _set_in_container(container: Any, key: Any, value: Any) -> None:
    if isinstance(container, list):
        idx = int(key)
        while len(container) <= idx:
            container.append(None)
        container[idx] = value
    elif isinstance(container, dict):
        container[key] = value
    else:
        raise TypeError(f"cannot set key {key!r} on {type(container).__name__}")


def _apply_set(root: dict, path: list, value: Any) -> None:
    if not path:
        raise ValueError("kind:1 requires a non-empty path")
    parent, key = _parent_and_key(root, path)
    _set_in_container(parent, key, value)


def _apply_push(root: dict, path: list, value: Any, i: int | None) -> tuple[int, int]:
    """Returns the half-open [start, end) index range the pushed items landed
    at, so provenance can later attribute this line to those indices."""
    if not path:
        raise ValueError("kind:2 requires a non-empty path")
    parent, key = _parent_and_key(root, path)
    if isinstance(parent, list):
        idx = int(key)
        while len(parent) <= idx:
            parent.append(None)
        if parent[idx] is None:
            parent[idx] = []
        arr = parent[idx]
    else:
        if key not in parent or parent[key] is None:
            parent[key] = []
        arr = parent[key]
    if not isinstance(arr, list):
        raise TypeError("kind:2 target is not an array")
    if i is not None:
        del arr[i:]
    start = len(arr)
    if value is not None:
        arr.extend(value)
    return (start, len(arr))


def _apply_delete(root: dict, path: list) -> None:
    if not path:
        raise ValueError("kind:3 requires a non-empty path")
    parent, key = _parent_and_key(root, path)
    if isinstance(parent, list):
        idx = int(key)
        if 0 <= idx < len(parent):
            del parent[idx]
        else:
            raise IndexError(f"delete index {idx} out of range (len {len(parent)})")
    elif isinstance(parent, dict):
        if key in parent:
            del parent[key]
        else:
            raise KeyError(f"delete key {key!r} not present")
    else:
        raise TypeError("kind:3 target parent is not a container")


def _find_truncation_markers(value: Any, path: tuple = ()) -> list[tuple[tuple, str]]:
    found: list[tuple[tuple, str]] = []
    if isinstance(value, str):
        if value.startswith(TRUNCATION_MARKER_PREFIX):
            found.append((path, value))
    elif isinstance(value, dict):
        for k, v in value.items():
            found.extend(_find_truncation_markers(v, path + (k,)))
    elif isinstance(value, list):
        for idx, v in enumerate(value):
            found.extend(_find_truncation_markers(v, path + (idx,)))
    return found


def _find_timestamps(value: Any, path: list | None = None) -> list[tuple[str, int]]:
    """Recursively collect epoch-ms timestamp fields from a pushed/set value,
    in the order they appear (depth-first, dict insertion order).

    A `kind:1` can set a bare scalar leaf (e.g. `k:["requests",0,"responseTimestamp"],
    v:500`), where the field name comes from the path, not from inside `value` -
    handled via `path`'s last segment on the top-level call only.
    """
    found: list[tuple[str, int]] = []
    if path and isinstance(value, int) and path[-1] in _TIMESTAMP_FIELDS:
        found.append((path[-1], value))
    if isinstance(value, dict):
        for k, v in value.items():
            if k in _TIMESTAMP_FIELDS and isinstance(v, int):
                found.append((k, v))
            else:
                found.extend(_find_timestamps(v))
    elif isinstance(value, list):
        for v in value:
            found.extend(_find_timestamps(v))
    return found
