"""Tests for kanban done command output parsing."""

from __future__ import annotations

from engine.application.kanban.done_result import (
    DONE_MERGE_OK_RE,
    UNDO_ERROR_RE,
    UNDO_STRATEGY_RESET,
    UNDO_STRATEGY_REVERT,
    UNDO_WORKTREE_RE,
    classify_done_failure,
)


def test_classify_done_warn_conflict() -> None:
    stdout = (
        "[WARN] worktree 병합 실패: 병합 충돌 발생: generic.py\n"
        "  - generic.py\n"
    )

    result = classify_done_failure(stdout, "")

    assert result["error_kind"] == "merge_conflict"
    assert result["conflicts"] == ["generic.py"]


def test_classify_done_dirty_worktree() -> None:
    stdout = (
        "[ERROR] 미커밋 변경이 있는 워크트리입니다. Done 전이를 차단합니다.\n"
        "  미커밋 파일 목록:\n"
        "    - dirty.py\n"
    )

    result = classify_done_failure(stdout, "")

    assert result["error_kind"] == "dirty_worktree"
    assert result["dirty_files"] == ["dirty.py"]


def test_classify_done_uses_stderr_fallback() -> None:
    result = classify_done_failure("", "fatal: merge failed")

    assert result["error_kind"] == "other"
    assert result["message"] == "fatal: merge failed"


def test_done_merge_success_regex_extracts_branch_and_sha() -> None:
    match = DONE_MERGE_OK_RE.search("feat/T-1-test -> develop 병합 완료 (abc12345)")

    assert match is not None
    assert match.group(1) == "feat/T-1-test"
    assert match.group(2) == "abc12345"


def test_undo_done_regexes_extract_strategy_worktree_and_error() -> None:
    assert UNDO_STRATEGY_RESET.search("[undo-done] 전략 1: reset --hard 진행")
    assert UNDO_STRATEGY_REVERT.search("[undo-done] 전략 2: revert -m 1 진행")

    worktree = UNDO_WORKTREE_RE.search(
        "[undo-done] 워크트리 재생성 완료: path=/tmp/wt branch=feat/T-1-test"
    )
    assert worktree is not None
    assert worktree.group(1) == "/tmp/wt"
    assert worktree.group(2) == "feat/T-1-test"

    error = UNDO_ERROR_RE.search("[undo-done] ERROR: failed")
    assert error is not None
    assert error.group(1) == "failed"

