"""Tests for conveyor complete command output parsing."""

from __future__ import annotations

from engine.application.conveyor.complete_result import (
    COMPLETE_MERGE_OK_RE,
    UNDO_ERROR_RE,
    UNDO_STRATEGY_RESET,
    UNDO_STRATEGY_REVERT,
    UNDO_WORKTREE_RE,
    classify_complete_failure,
)


def test_classify_complete_warn_conflict() -> None:
    stdout = (
        "[WARN] worktree merge failed: merging conflict occur: generic.py\\n"
        "  - generic.py\n"
    )

    result = classify_complete_failure(stdout, "")

    assert result["error_kind"] == "merge_conflict"
    assert result["conflicts"] == ["generic.py"]


def test_classify_complete_dirty_worktree() -> None:
    stdout = (
        "[ERROR] It is a work tree that changes the MIT. Complete Blocks All. \\n"
        "Micommit File List:\\n"
        "    - dirty.py\n"
    )

    result = classify_complete_failure(stdout, "")

    assert result["error_kind"] == "dirty_worktree"
    assert result["dirty_files"] == ["dirty.py"]


def test_classify_complete_uses_stderr_fallback() -> None:
    result = classify_complete_failure("", "fatal: merge failed")

    assert result["error_kind"] == "other"
    assert result["message"] == "fatal: merge failed"


def test_complete_merge_success_regex_extracts_branch_and_sha() -> None:
    match = COMPLETE_MERGE_OK_RE.search("feat/WR-1-test -> Complete development merge (abc12345)")

    assert match is not None
    assert match.group(1) == "feat/WR-1-test"
    assert match.group(2) == "abc12345"


def test_undo_complete_regexes_extract_strategy_worktree_and_error() -> None:
    assert UNDO_STRATEGY_RESET.search("[undo-complete] Strategy 1: reset --hard progress")
    assert UNDO_STRATEGY_REVERT.search("[undo-complete] Strategy 2: revert -m 1 Progress")

    worktree = UNDO_WORKTREE_RE.search(
        "[undo-complete] Worktree Regeneration: path=/tmp/wt branch=feat/WR-1-test"
    )
    assert worktree is not None
    assert worktree.group(1) == "/tmp/wt"
    assert worktree.group(2) == "feat/WR-1-test"

    error = UNDO_ERROR_RE.search("[undo-complete] ERROR: failed")
    assert error is not None
    assert error.group(1) == "failed"
