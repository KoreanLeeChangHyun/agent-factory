"""Tests for pure worktree path rules."""

from __future__ import annotations

from pathlib import Path

from engine.core.worktrees.paths import (
    merge_lock_path,
    normalize_ticket_number,
    worktree_dir_name,
    worktree_path_for_branch,
    worktrees_base_dir,
)


def test_normalize_ticket_number_adds_prefix_once() -> None:
    assert normalize_ticket_number("123") == "T-123"
    assert normalize_ticket_number("T-123") == "T-123"


def test_worktree_dir_name_replaces_branch_separator() -> None:
    assert worktree_dir_name("feat/T-123-example") == "feat-T-123-example"


def test_worktree_paths_are_under_agent_factory_root(tmp_path: Path) -> None:
    assert worktrees_base_dir(tmp_path) == tmp_path / ".agent-factory" / "worktrees"
    assert merge_lock_path(tmp_path) == tmp_path / ".git" / "worktree-merge.lockdir"
    assert (
        worktree_path_for_branch(tmp_path, "feat/T-123-example")
        == tmp_path / ".agent-factory" / "worktrees" / "feat-T-123-example"
    )

