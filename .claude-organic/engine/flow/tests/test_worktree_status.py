"""test_worktree_status.py — worktree_status 단위 테스트 (T-419 / T4)

4개 시나리오를 통해 핵심 헬퍼 함수들과 미존재 케이스를 검증한다:
  TC1: lock 마커 파일 존재 → _is_locked() == True
  TC2: modified 1건 + untracked 1건 → uncommitted_count/modified/untracked 분류
  TC3: feature 브랜치 commit 3건 → feature_commits==3, base_diff ahead==3
  TC4: 존재하지 않는 ticket 조회 → exists==False schema 반환

한글 브랜치명 안전 처리: TC3 setUp 에서 feat/T-001-한글-테스트 브랜치 사용.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# sys.path: .claude-organic/engine 을 포함시켜 flow 패키지 import 가능하게 한다
_ENGINE_DIR = str(Path(__file__).resolve().parent.parent.parent)
if _ENGINE_DIR not in sys.path:
    sys.path.insert(0, _ENGINE_DIR)

from flow.worktree_status import (
    _base_diff,
    _classify_porcelain,
    _empty_status,
    _is_locked,
    _uncommitted_breakdown,
    get_worktree_status,
)


def _git(repo: str, *args: str) -> subprocess.CompletedProcess[str]:
    """임시 git 저장소를 대상으로 git 명령을 실행한다."""
    return subprocess.run(
        ["git", "-C", repo] + list(args),
        capture_output=True,
        text=True,
    )


def _setup_bare_repo(tmpdir: str) -> str:
    """기본 develop 브랜치를 갖는 임시 git 저장소를 초기화하고 반환한다."""
    repo = tmpdir
    _git(repo, "init", "-b", "develop")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    init_file = os.path.join(repo, "README.md")
    with open(init_file, "w", encoding="utf-8") as f:
        f.write("init\n")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "init")
    return repo


class TestLockDetection(unittest.TestCase):
    """TC1: lock 마커 파일이 존재하면 _is_locked() == True."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.mkdtemp(prefix="wf_test_lock_")
        self.main_repo = os.path.join(self._tmpdir, "main")
        os.makedirs(self.main_repo)
        _setup_bare_repo(self.main_repo)

        # git worktree add 로 실제 worktree 생성
        self.wt_path = os.path.join(self._tmpdir, "wt_lock")
        result = _git(
            self.main_repo,
            "worktree", "add", self.wt_path, "-b", "feat/T-lock-test",
        )
        self.assertEqual(result.returncode, 0, f"worktree add 실패: {result.stderr}")

    def tearDown(self) -> None:
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_lock_file_detected(self) -> None:
        """TC1: .git/worktrees/<dir>/locked 마커 생성 → _is_locked() == True."""
        # git rev-parse --git-common-dir 로 common .git 경로 파악
        result = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            cwd=self.wt_path,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)
        common_dir = result.stdout.strip()
        if not os.path.isabs(common_dir):
            common_dir = os.path.normpath(os.path.join(self.wt_path, common_dir))

        dir_name = os.path.basename(os.path.normpath(self.wt_path))
        locked_marker = os.path.join(common_dir, "worktrees", dir_name, "locked")

        # locked 마커 파일 생성 (touch)
        os.makedirs(os.path.dirname(locked_marker), exist_ok=True)
        with open(locked_marker, "w") as f:
            f.write("")

        self.assertTrue(
            _is_locked(self.wt_path),
            "lock 마커 파일 존재 시 _is_locked() 는 True를 반환해야 한다",
        )


class TestUncommittedBreakdown(unittest.TestCase):
    """TC2: modified 1건 + untracked 1건 → uncommitted_count/modified/untracked 정확 분류."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.mkdtemp(prefix="wf_test_uncommitted_")
        self.main_repo = os.path.join(self._tmpdir, "main")
        os.makedirs(self.main_repo)
        _setup_bare_repo(self.main_repo)

        self.wt_path = os.path.join(self._tmpdir, "wt_uncommitted")
        result = _git(
            self.main_repo,
            "worktree", "add", self.wt_path, "-b", "feat/T-uncommitted-test",
        )
        self.assertEqual(result.returncode, 0, f"worktree add 실패: {result.stderr}")

    def tearDown(self) -> None:
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_uncommitted_count_and_breakdown(self) -> None:
        """TC2: modified 1건 + untracked 1건 → 총 2건, 분류 각각 1."""
        # modified: worktree 내 기존 파일(README.md) 수정 후 git add
        readme = os.path.join(self.wt_path, "README.md")
        with open(readme, "a", encoding="utf-8") as f:
            f.write("modified line\n")
        _git(self.wt_path, "add", "README.md")

        # untracked: 새 파일 생성 (add 하지 않음)
        untracked = os.path.join(self.wt_path, "new_untracked.py")
        with open(untracked, "w", encoding="utf-8") as f:
            f.write("# untracked\n")

        result = _uncommitted_breakdown(self.wt_path)

        self.assertEqual(
            result["count"], 2,
            f"uncommitted_count 는 2여야 한다, 실제: {result}",
        )
        self.assertEqual(
            result["modified"], 1,
            f"modified 는 1이어야 한다, 실제: {result}",
        )
        self.assertEqual(
            result["untracked"], 1,
            f"untracked 는 1이어야 한다, 실제: {result}",
        )


class TestCommitCount(unittest.TestCase):
    """TC3: feature 브랜치에 commit 3건 → feature_commits==3, base_diff ahead==3.

    한글 포함 브랜치명(feat/T-001-한글-테스트)으로 한글 경로 안전 처리 검증.
    """

    def setUp(self) -> None:
        self._tmpdir = tempfile.mkdtemp(prefix="wf_test_commits_")
        self.main_repo = os.path.join(self._tmpdir, "main")
        os.makedirs(self.main_repo)
        _setup_bare_repo(self.main_repo)

        # 한글 포함 feature 브랜치명으로 worktree 생성
        self.wt_path = os.path.join(self._tmpdir, "wt_commits")
        self.branch_name = "feat/T-001-한글-테스트"
        result = _git(
            self.main_repo,
            "worktree", "add", self.wt_path, "-b", self.branch_name,
        )
        self.assertEqual(result.returncode, 0, f"worktree add 실패: {result.stderr}")

        # feature 브랜치에 commit 3건 추가
        for i in range(1, 4):
            fpath = os.path.join(self.wt_path, f"file_{i}.py")
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(f"# commit {i}\n")
            _git(self.wt_path, "add", f"file_{i}.py")
            result = _git(
                self.wt_path, "commit", "-m", f"feat: 작업 {i}번 커밋",
            )
            self.assertEqual(result.returncode, 0, f"commit {i} 실패: {result.stderr}")

    def tearDown(self) -> None:
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_feature_commits_ahead(self) -> None:
        """TC3: develop 분기 후 commit 3건 → ahead==3."""
        diff = _base_diff(self.wt_path, base="develop")

        self.assertEqual(
            diff["ahead"], 3,
            f"develop 대비 ahead 는 3이어야 한다, 실제: {diff}",
        )
        self.assertEqual(
            diff["behind"], 0,
            f"develop 대비 behind 는 0이어야 한다, 실제: {diff}",
        )

    def test_classify_porcelain_passthrough(self) -> None:
        """TC3 부가: 한글 파일명을 포함한 porcelain 출력도 정확히 분류된다."""
        # 한글 파일명 untracked 생성
        han_path = os.path.join(self.wt_path, "한글파일.py")
        with open(han_path, "w", encoding="utf-8") as f:
            f.write("# 한글 파일\n")

        # git status --porcelain 으로 raw 출력 확인
        proc = subprocess.run(
            ["git", "-C", self.wt_path, "status", "--porcelain"],
            capture_output=True,
            text=True,
        )
        total, modified, untracked = _classify_porcelain(proc.stdout)
        self.assertEqual(untracked, 1, "한글 파일명 untracked 1건이어야 한다")
        self.assertEqual(modified, 0)


class TestWorktreeNotExists(unittest.TestCase):
    """TC4: 존재하지 않는 ticket 조회 → exists==False schema 반환."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.mkdtemp(prefix="wf_test_notexists_")
        self.main_repo = os.path.join(self._tmpdir, "main")
        os.makedirs(self.main_repo)
        _setup_bare_repo(self.main_repo)

    def tearDown(self) -> None:
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_nonexistent_ticket_returns_empty_schema(self) -> None:
        """TC4: T-XXX 존재하지 않는 ticket → exists==False, 나머지 필드 default."""
        result = get_worktree_status("T-XXX", repo_path=self.main_repo)

        # None 반환 금지 (T1 결정: always dict)
        self.assertIsNotNone(result, "get_worktree_status 는 None 을 반환하지 않는다")
        assert result is not None  # mypy narrowing

        self.assertFalse(
            result.get("exists"),
            f"미존재 ticket 은 exists==False 여야 한다, 실제: {result}",
        )
        # schema 완전성 검증
        for key in ("ticket", "path", "lock", "uncommitted_count", "uncommitted",
                    "feature_commits", "head", "base_diff", "branch"):
            self.assertIn(key, result, f"응답 schema 에 '{key}' 필드가 없다")

        self.assertEqual(result["ticket"], "T-XXX")
        self.assertEqual(result["path"], "")
        self.assertFalse(result["lock"])
        self.assertEqual(result["uncommitted_count"], 0)
        self.assertEqual(result["uncommitted"]["modified"], 0)
        self.assertEqual(result["uncommitted"]["untracked"], 0)
        self.assertEqual(result["feature_commits"], 0)
        self.assertEqual(result["head"], "")

    def test_empty_status_helper_schema(self) -> None:
        """TC4 부가: _empty_status 헬퍼가 T1 합의 schema 를 정확히 반환한다."""
        s = _empty_status("T-999")
        self.assertEqual(s["ticket"], "T-999")
        self.assertFalse(s["exists"])
        self.assertEqual(s["uncommitted_count"], 0)
        self.assertEqual(s["uncommitted"], {"modified": 0, "untracked": 0})
        self.assertEqual(s["feature_commits"], 0)
        self.assertIn("base_diff", s)
        self.assertEqual(s["base_diff"]["ahead"], 0)
        self.assertEqual(s["base_diff"]["behind"], 0)


if __name__ == "__main__":
    unittest.main()
