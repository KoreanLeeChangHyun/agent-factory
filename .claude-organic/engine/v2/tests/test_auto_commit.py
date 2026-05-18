"""test_auto_commit.py — Stage 3-E §0.1 결정론 commit 단위 테스트.

대상: `_common.auto_commit(ctx)` — WORK 종료 직후 driver 가 호출하는 결정론 git
add + commit 헬퍼. LLM 위임 0건.

검증 분기:
  1. worktree_path=None → skip (return 0)
  2. worktree path 미존재 → skip (return 0)
  3. staged 변경 0건 → skip (return 0)
  4. staged 변경 있음 → commit 성공 (return 0, HEAD 1 이동)
"""

from __future__ import annotations

import subprocess
from pathlib import Path


from engine.v2._common import WorkflowContext, auto_commit


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def _init_repo(tmp_path: Path) -> Path:
    """tmp_path 안에 minimal git repo 생성 + initial commit."""
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
        title="smoke 티켓",
    )


def test_auto_commit_worktree_less_skips(tmp_path: Path) -> None:
    """worktree_path=None → skip, return 0, 로그에 'worktree-less' 라인."""
    ctx = _make_ctx(tmp_path, worktree_path=None)
    rc = auto_commit(ctx)
    assert rc == 0
    log = ctx.workflow_log_path().read_text(encoding="utf-8")
    assert "AUTO-COMMIT" in log
    assert "worktree-less" in log


def test_auto_commit_worktree_path_missing(tmp_path: Path) -> None:
    """worktree_path 가 존재하지 않는 디렉터리 → skip."""
    missing = tmp_path / "does-not-exist"
    ctx = _make_ctx(tmp_path, worktree_path=missing)
    rc = auto_commit(ctx)
    assert rc == 0
    log = ctx.workflow_log_path().read_text(encoding="utf-8")
    assert "미존재" in log


def test_auto_commit_no_staged_changes_skips(tmp_path: Path) -> None:
    """worktree 가 clean 상태 → staged 변경 0건 → skip."""
    repo = _init_repo(tmp_path)
    ctx = _make_ctx(tmp_path, worktree_path=repo)
    head_before = _git(repo, "rev-parse", "HEAD").stdout.strip()
    rc = auto_commit(ctx)
    assert rc == 0
    head_after = _git(repo, "rev-parse", "HEAD").stdout.strip()
    assert head_before == head_after, "변경 0건인데 commit 발생"
    log = ctx.workflow_log_path().read_text(encoding="utf-8")
    assert "0건" in log or "skip" in log


def test_auto_commit_with_changes_commits(tmp_path: Path) -> None:
    """worktree 안에 untracked 파일 추가 → auto_commit → HEAD 1 이동 + 메시지 template."""
    repo = _init_repo(tmp_path)
    (repo / "sample.txt").write_text("hello\n", encoding="utf-8")
    ctx = _make_ctx(tmp_path, worktree_path=repo)
    head_before = _git(repo, "rev-parse", "HEAD").stdout.strip()
    rc = auto_commit(ctx)
    assert rc == 0
    head_after = _git(repo, "rev-parse", "HEAD").stdout.strip()
    assert head_before != head_after, "변경 있는데 commit 미발생"
    # 메시지 template 검증
    msg = _git(repo, "log", "-1", "--pretty=%s").stdout.strip()
    assert "T-493" in msg
    assert "smoke 티켓" in msg
    assert "v2 driver auto-commit" in msg


def test_auto_commit_modified_tracked_file(tmp_path: Path) -> None:
    """tracked 파일 수정 → staged → commit."""
    repo = _init_repo(tmp_path)
    (repo / "README.md").write_text("modified\n", encoding="utf-8")
    ctx = _make_ctx(tmp_path, worktree_path=repo)
    head_before = _git(repo, "rev-parse", "HEAD").stdout.strip()
    rc = auto_commit(ctx)
    assert rc == 0
    head_after = _git(repo, "rev-parse", "HEAD").stdout.strip()
    assert head_before != head_after
