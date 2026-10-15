"""Recomputes VS Code's workspaceStorage/<hash> folder name from a folder
path, per the formula in notes.md (source: workspaces.ts,
getSingleFolderWorkspaceIdentifier; re-verified on Windows in experiment 02):

  local folder (file scheme):  md5(fsPath + ctime)
    Windows: ctime = floor(birthtimeMs)   macOS: ctime = birthtime.getTime()
    Linux:   ctime = inode (birthtime is unusable there)
    If there's no ctime/inode, just md5(fsPath).
  remote folder (non-file scheme, e.g. WSL/SSH): md5(uri.toString()), no salt.

This module is a pure calculator - it never reads the filesystem itself.
The investigator supplies the path and creation time/inode (e.g. from a
forensic image's timestamps, or a live `Get-Item`/`stat` on their own
machine); this just reproduces the hash. Because there's real ambiguity in
exactly how VS Code's fsPath is cased (experiment 02's worked example only
lowercases the drive letter, not the whole path), this returns a small set
of plausible variants rather than one answer, so the investigator can see
which one actually matches a real folder name.
"""

from __future__ import annotations

import hashlib


def _md5(s: str) -> str:
    return hashlib.md5(s.encode("utf-8")).hexdigest()


def compute_variants(
    path: str,
    os_type: str,
    ctime_ms: int | None = None,
    inode: int | None = None,
) -> list[dict]:
    path = path or ""
    seen: dict[str, str] = {}  # input_string -> label (first one wins, dedup by string)

    def add(label: str, input_string: str) -> None:
        if input_string not in seen:
            seen[input_string] = label

    if os_type in ("windows", "macos"):
        salt = str(ctime_ms) if ctime_ms not in (None, "") else ""
        drive_lowered = (path[:1].lower() + path[1:]) if path else path
        add("as typed", path + salt)
        add("drive letter lowercased (VS Code's own fsPath convention)", drive_lowered + salt)
        add("whole path lowercased", path.lower() + salt)
        if not salt:
            add("no creation time given - path only", path)
    elif os_type == "linux":
        salt = str(inode) if inode not in (None, "") else ""
        add("path + inode" if salt else "no inode given - path only", path + salt)
    elif os_type == "remote":
        add("URI string only (no stat salt)", path)
    else:
        add("unrecognised folder type - path only, no salt", path)

    return [{"label": label, "input": s, "md5": _md5(s)} for s, label in seen.items()]
