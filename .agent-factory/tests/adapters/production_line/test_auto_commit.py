"""test auto commit.py — Stage 3-E §0.1 Decision Commit Unit Test.

Target: ` common.auto commit(ctx)` — Determined git calling driver after WORK end
add + commit helper. 0 LLM commission.

Payment Terms:
  1. worktree_path=None → skip (return 0)
  2. worktree path (return 0)
  3. FAQs skip (return 0)
  4. FAQs Staged Changes → Commit Success (return 0, Head 1 Move)
"""

from __future__ import annotations

import subprocess
from pathlib import Path


from engine.apps.production_line._common import WorkflowContext, auto_commit


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def _init_repo(tmp_path: Path) -> Path:
    """create minimal git repo within tmp path + initial commit."""
    repo = tmp_path / "wt"
    repo.mkdir()
    assert _git(repo, "init", "--initial-branch=main").returncode == 0
    assert _git(repo, "config", "user.email", "t@e.t").returncode == 0
    assert _git(repo, "config", "user.name", "Test").returncode == 0
    (repo / "README.md").write_text("init\n", encoding="utf-8")
    assert _git(repo, "add", "README.md").returncode == 0
    assert _git(repo, "commit", "-m", "init").returncode == 0
    return repo


def _make_ctx(tmp_path: Path, *, worktree_path: Path | None) -> WorkflowContext:
    work_dir = tmp_path / "run"
    work_dir.mkdir(exist_ok=True)
    return WorkflowContext(
        ticket_no="T-493",
        registry_key="20260515-000000",
        work_dir=work_dir,
        command="implement",
        mode="multi",
        current_step="WORK",
        feature_branch="feat/T-493-smoke" if worktree_path else None,
        worktree_path=worktree_path,
        title="Smoke tickets",
    )


def test_auto_commit_worktree_less_skips(tmp_path: Path) -> None:
    """worktree path=None → skip, return 0, 'worktree-less' line on the log."""
    ctx = _make_ctx(tmp_path, worktree_path=None)
    rc = auto_commit(ctx)
    assert rc == 0
    log = ctx.workflow_log_path().read_text(encoding="utf-8")
    assert "AUTO-COMMIT" in log
    assert "worktree-less" in log


def test_auto_commit_worktree_path_missing(tmp_path: Path) -> None:
    """worktree path does not exist directory → skip."""
    missing = tmp_path / "does-not-exist"
    ctx = _make_ctx(tmp_path, worktree_path=missing)
    rc = auto_commit(ctx)
    assert rc == 0
    log = ctx.workflow_log_path().read_text(encoding="utf-8")
    assert "About Us" in log


def test_auto_commit_no_staged_changes_skips(tmp_path: Path) -> None:
    """worktree is clean condition → staged change 0 → skip."""
    repo = _init_repo(tmp_path)
    ctx = _make_ctx(tmp_path, worktree_path=repo)
    head_before = _git(repo, "rev-parse", "HEAD").stdout.strip()
    rc = auto_commit(ctx)
    assert rc == 0
    head_after = _git(repo, "rev-parse", "HEAD").stdout.strip()
    assert head_before == head_after, "0 Changes"
    log = ctx.workflow_log_path().read_text(encoding="utf-8")
    assert "0 items" in log or "skip" in log


def test_auto_commit_with_changes_commits(tmp_path: Path) -> None:
    """Add untracked file inside worktree → auto commit → HEAD 1 go + message template."""
    repo = _init_repo(tmp_path)
    (repo / "sample.txt").write_text("hello\n", encoding="utf-8")
    ctx = _make_ctx(tmp_path, worktree_path=repo)
    head_before = _git(repo, "rev-parse", "HEAD").stdout.strip()
    rc = auto_commit(ctx)
    assert rc == 0
    head_after = _git(repo, "rev-parse", "HEAD").stdout.strip()
    assert head_before != head_after, "Changes Commit"
    # Query template validation
    msg = _git(repo, "log", "-1", "--pretty=%s").stdout.strip()
    assert "T-493" in msg
    assert "Smoke tickets" in msg
    assert "production-line auto-commit" in msg


def test_auto_commit_modified_tracked_file(tmp_path: Path) -> None:
    """tracked file fixes → staged → commit."""
    repo = _init_repo(tmp_path)
    (repo / "README.md").write_text("modified\n", encoding="utf-8")
    ctx = _make_ctx(tmp_path, worktree_path=repo)
    head_before = _git(repo, "rev-parse", "HEAD").stdout.strip()
    rc = auto_commit(ctx)
    assert rc == 0
    head_after = _git(repo, "rev-parse", "HEAD").stdout.strip()
    assert head_before != head_after
