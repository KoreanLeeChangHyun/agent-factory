"""Worktree status — Conveyor card uncommitted indicator + commit action.

T-419 diagnostic tool is a value-less waste paper (commit 99c9ce0). This module is a workflow
If the user is missing (Watcher Commit), click on the Finder button.
Simplified Easter version to allow instant commit.

Public API:
    get all uncommitted: WorkRequest + uncommitted count list
    commit worktree: git add -A &&git commit -m executed in worktree
"""

from __future__ import annotations

import os
import subprocess
import sys

_engine_dir: str = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
)
if _engine_dir not in sys.path:
    sys.path.insert(0, _engine_dir)

from flow.worktree_manager import (  # noqa: E402
    get_worktree_path,
    is_worktree_enabled,
    list_worktrees,
)


def _count_uncommitted(worktree_path: str) -> int:
    """Returns the number of files modified + untracked.

    git status --porcelain line counting. 0 polybags when failed.
    """
    if not os.path.isdir(worktree_path):
        return 0
    try:
        result = subprocess.run(
            ["git", "-C", worktree_path, "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (subprocess.TimeoutExpired, OSError):
        return 0
    if result.returncode != 0:
        return 0
    return sum(1 for line in result.stdout.splitlines() if line.strip())


def get_all_uncommitted() -> list[dict]:
    """Return of the full work tree’s mitigation count list (for card indicator batch query).

    Returns:
        [{work_request, path, uncommitted_count}, ...] — empty list when worktree mode is disabled.
    """
    if not is_worktree_enabled():
        return []
    items: list[dict] = []
    for wt in list_worktrees():
        if not wt.ticket_number:
            continue
        items.append(
            {
                "work_request": wt.ticket_number,
                "path": wt.path,
                "uncommitted_count": _count_uncommitted(wt.path),
            }
        )
    return items


def commit_worktree(work_request: str, message: str | None = None) -> dict:
    """git add -A && git commit -m <msg> in the work tree.

    User manual dehumidification paths when workflow regression (unloading of water commit).
    'wip(WR-NNN): pending worktree changes`
    Log in

    Returns:
        {ok: bool, work_request, path, message, stdout?} | {ok: False, error}
    """
    if not work_request.startswith("WR-"):
        work_request = f"WR-{work_request}"
    wt_path = get_worktree_path(work_request)
    if not wt_path or not os.path.isdir(wt_path):
        return {"ok": False, "error": f"worktree not found for {work_request}"}

    if not message or not message.strip():
        message = f"wip({work_request}): pending worktree changes"

    add = subprocess.run(
        ["git", "-C", wt_path, "add", "-A"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if add.returncode != 0:
        return {
            "ok": False,
            "error": f"git add failed: {add.stderr.strip() or add.stdout.strip()}",
        }

    commit = subprocess.run(
        ["git", "-C", wt_path, "commit", "-m", message],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if commit.returncode != 0:
        return {
            "ok": False,
            "error": (
                f"git commit failed: "
                f"{commit.stderr.strip() or commit.stdout.strip() or 'nothing to commit'}"
            ),
        }

    return {
        "ok": True,
        "work_request": work_request,
        "path": wt_path,
        "message": message,
        "stdout": commit.stdout.strip(),
    }
