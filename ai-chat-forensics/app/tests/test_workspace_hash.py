"""Tests for the workspace-hash calculator. The formula is confirmed
[observed] against the one documented worked example in notes.md (see
test_matches_the_confirmed_notes_md_example below) - a past attempt to
re-verify this produced a false "unconfirmed" result due to a bug in the
verification script itself (an un-doubled backslash silently parsed as a
carriage-return escape), not the formula; see notes.md's 2026-10-15
correction. Most of the tests below still check shape/never-crashes rather
than exact values, since variants beyond the one confirmed case are not
independently verified against a real folder."""

import hashlib

from parser.workspace_hash import compute_variants


def test_matches_the_confirmed_notes_md_example():
    """The one real-world confirmation this formula has: experiment 02
    recomputed the hash for C:\\dev\\research with a known creation time and
    it matched the real workspaceStorage folder name on disk. [observed]"""
    variants = compute_variants("C:\\dev\\research", "windows", ctime_ms=1792008626997)
    hashes = {v["md5"] for v in variants}
    assert "211a3faf4e627877bf03f662f79cfec8" in hashes


def test_windows_variants_use_documented_formula_shape():
    variants = compute_variants("C:\\dev\\research", "windows", ctime_ms=1792008626997)
    inputs = {v["input"] for v in variants}
    assert "C:\\dev\\research1792008626997" in inputs  # as typed
    assert "c:\\dev\\research1792008626997" in inputs  # drive-lowered
    for v in variants:
        assert v["md5"] == hashlib.md5(v["input"].encode("utf-8")).hexdigest()


def test_windows_with_no_ctime_hashes_path_only():
    variants = compute_variants("C:\\dev\\research", "windows", ctime_ms=None)
    assert any(v["input"] == "C:\\dev\\research" for v in variants)


def test_linux_uses_inode_not_ctime():
    variants = compute_variants("/home/user/project", "linux", inode=123456)
    assert any(v["input"] == "/home/user/project123456" for v in variants)


def test_remote_hashes_uri_with_no_salt_even_if_ctime_given():
    """A remote (WSL/SSH) folder is hashed as md5(uri) with no stat salt at
    all per notes.md - ctime/inode must be ignored even if someone fills
    them in by mistake."""
    variants = compute_variants(
        "file:///home/user/project", "remote", ctime_ms=999999, inode=42
    )
    assert len(variants) == 1
    assert variants[0]["input"] == "file:///home/user/project"


def test_empty_path_does_not_crash():
    variants = compute_variants("", "windows", ctime_ms=123)
    assert isinstance(variants, list)


def test_variants_are_deduplicated_by_input_string():
    # drive-lowered and as-typed collapse to the same string for an
    # already-lowercase path - should not produce duplicate rows
    variants = compute_variants("c:\\dev\\research", "windows", ctime_ms=1)
    inputs = [v["input"] for v in variants]
    assert len(inputs) == len(set(inputs))
