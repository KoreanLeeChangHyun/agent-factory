"""Pure worktree path and identifier rules."""

from __future__ import annotations

from pathlib import Path


WORKTREES_DIR_NAME = Path(".agent-factory") / "worktrees"
MERGE_LOCK_NAME = "worktree-merge.lockdir"


def normalize_ticket_number(ticket_number: str) -> str:
    return ticket_number if ticket_number.startswith("T-") else f"T-{ticket_number}"


def worktree_dir_name(branch_name: str) -> str:
    """Convert a feature branch name into a filesystem-safe worktree dirname."""
    return branch_name.replace("/", "-")


def worktrees_base_dir(repo_path: str | Path) -> Path:
    return Path(repo_path) / WORKTREES_DIR_NAME


def merge_lock_path(repo_path: str | Path) -> Path:
    return Path(repo_path) / ".git" / MERGE_LOCK_NAME


def worktree_path_for_branch(repo_path: str | Path, branch_name: str) -> Path:
    return worktrees_base_dir(repo_path) / worktree_dir_name(branch_name)

