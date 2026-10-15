"""CLAUDE.md privacy rule: this app must never make outbound network calls.
Static check (not a runtime check) that nothing under app/ imports a module
that could reach the network - catches the mistake at commit time rather
than hoping no one calls it."""

import ast
import pathlib

# Full dotted module names (or exact prefixes) that can reach the network.
# `urllib.parse` is deliberately NOT here: it's pure string parsing (used to
# decode file:// URIs already present in parsed data) with no I/O capability
# at all - banning the whole `urllib` namespace would be punishing the wrong
# thing. `http` alone (the status-code/cookie constants module) is likewise
# fine; only its network-capable submodules are listed.
FORBIDDEN_MODULES = {
    "requests", "urllib.request", "urllib.error", "urllib2", "httpx",
    "http.client", "socket", "ftplib", "smtplib", "telnetlib", "aiohttp",
}

APP_DIR = pathlib.Path(__file__).resolve().parents[1]

# Only scan this project's own code - never a local virtualenv, __pycache__,
# or similar tooling directory a developer's machine happens to have under
# app/ (those hold third-party library code we don't control).
_EXCLUDED_DIR_NAMES = {".venv", "venv", "env", "__pycache__", ".pytest_cache", "site-packages"}


def _iter_py_files():
    for path in APP_DIR.rglob("*.py"):
        if _EXCLUDED_DIR_NAMES.isdisjoint(path.relative_to(APP_DIR).parts):
            yield path


def _is_forbidden(module_name: str) -> bool:
    return any(module_name == m or module_name.startswith(m + ".") for m in FORBIDDEN_MODULES)


def test_no_outbound_network_imports_anywhere_in_app():
    violations = []
    for path in _iter_py_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if _is_forbidden(alias.name):
                        violations.append(f"{path.relative_to(APP_DIR)}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                if _is_forbidden(node.module):
                    violations.append(f"{path.relative_to(APP_DIR)}: from {node.module} import ...")
    assert violations == [], f"outbound network imports found: {violations}"
