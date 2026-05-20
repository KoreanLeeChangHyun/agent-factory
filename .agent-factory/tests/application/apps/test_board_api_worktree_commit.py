"""Tests for Worktree Commit board API app boundary."""

from __future__ import annotations

from board.server.handlers.worktree_commit import (
    WorktreeCommitHandlerMixin as CompatWorktreeCommitHandlerMixin,
)
from engine.apps.board_api.worktree_commit import WorktreeCommitHandlerMixin


def test_worktree_commit_handler_compat_export_matches_app_boundary() -> None:
    assert CompatWorktreeCommitHandlerMixin is WorktreeCommitHandlerMixin


def test_worktree_commit_handler_exposes_expected_endpoint_methods() -> None:
    assert hasattr(WorktreeCommitHandlerMixin, "_handle_worktree_uncommitted_all")
    assert hasattr(WorktreeCommitHandlerMixin, "_handle_worktree_commit")
