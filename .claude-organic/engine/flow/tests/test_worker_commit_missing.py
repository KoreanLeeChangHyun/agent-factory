"""test_worker_commit_missing.py - 워커 commit 누락 탐지 단위 테스트 (T-411 회귀 차단)

4개 시나리오를 통해 count_feature_branch_commits 와 AND 조건 신호를 검증한다:
  TC1: feature 브랜치에 커밋 없음 → count == 0
  TC2: feature 브랜치에 커밋 1건 → count == 1
  TC3: 존재하지 않는 브랜치 → count == -1 (검사 불가)
  TC4: untracked 파일 + commit 0 → AND 조건 신호 확인 (T-411 핵심 시나리오)
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

from flow.worktree_manager import count_feature_branch_commits, has_uncommitted_changes


def _git(repo: str, *args: str) -> subprocess.CompletedProcess[str]:
    """임시 git 저장소를 대상으로 git 명령을 실행한다."""
    return subprocess.run(
        ["git", "-C", repo] + list(args),
        capture_output=True,
        text=True,
    )


class TestWorkerCommitMissingDetection(unittest.TestCase):
    """count_feature_branch_commits 와 has_uncommitted_changes AND 조건 검증."""

    def setUp(self) -> None:
        """격리된 임시 git 저장소를 생성하고 feature 브랜치를 분기한다."""
        self.repo = tempfile.mkdtemp(prefix="wf_test_commit_missing_")
        # git init
        _git(self.repo, "init", "-b", "develop")
        # git config (테스트 환경용 최소 설정)
        _git(self.repo, "config", "user.email", "test@example.com")
        _git(self.repo, "config", "user.name", "Test")
        # develop 브랜치에 초기 커밋 생성
        init_file = os.path.join(self.repo, "README.md")
        with open(init_file, "w") as f:
            f.write("init\n")
        _git(self.repo, "add", "README.md")
        _git(self.repo, "commit", "-m", "init")
        # feature 브랜치 생성
        _git(self.repo, "checkout", "-b", "feat/T-999-test")

    def tearDown(self) -> None:
        shutil.rmtree(self.repo, ignore_errors=True)

    def test_count_zero_when_no_worker_commit(self) -> None:
        """TC1: feature 브랜치에 커밋 없이 untracked 파일만 → count == 0."""
        untracked = os.path.join(self.repo, "new_file.py")
        with open(untracked, "w") as f:
            f.write("# new\n")
        # add/commit 없이 count 만 조회
        count = count_feature_branch_commits(
            "feat/T-999-test", base_branch="develop", repo_path=self.repo
        )
        self.assertEqual(count, 0, "커밋 없는 feature 브랜치는 0을 반환해야 한다")

    def test_count_positive_after_commit(self) -> None:
        """TC2: feature 브랜치에 커밋 1건 → count == 1."""
        work_file = os.path.join(self.repo, "work.py")
        with open(work_file, "w") as f:
            f.write("x = 1\n")
        _git(self.repo, "add", "work.py")
        _git(self.repo, "commit", "-m", "feat: add work")
        count = count_feature_branch_commits(
            "feat/T-999-test", base_branch="develop", repo_path=self.repo
        )
        self.assertEqual(count, 1, "커밋 1건인 feature 브랜치는 1을 반환해야 한다")

    def test_count_negative_for_missing_branch(self) -> None:
        """TC3: 존재하지 않는 브랜치 → count == -1 (검사 불가, 차단 금지)."""
        count = count_feature_branch_commits(
            "feat/T-000-missing", base_branch="develop", repo_path=self.repo
        )
        self.assertEqual(count, -1, "존재하지 않는 브랜치는 -1을 반환해야 한다")

    def test_uncommitted_and_zero_commit_combo(self) -> None:
        """TC4: untracked 파일 + commit 0 → AND 조건 신호 확인 (T-411 핵심 시나리오).

        has_uncommitted_changes == True AND count_feature_branch_commits == 0 이
        동시에 충족될 때 워커 commit 누락 신호가 발생한다.
        """
        untracked = os.path.join(self.repo, "worker_output.py")
        with open(untracked, "w") as f:
            f.write("# worker wrote this but forgot to commit\n")

        uncommitted = has_uncommitted_changes(self.repo)
        count = count_feature_branch_commits(
            "feat/T-999-test", base_branch="develop", repo_path=self.repo
        )

        self.assertTrue(uncommitted, "untracked 파일이 있으면 uncommitted=True여야 한다")
        self.assertEqual(count, 0, "add/commit 없는 feature 브랜치는 commit_count=0이어야 한다")

        # AND 조건 검증 — 두 신호 모두 충족 시 워커 commit 누락으로 판단
        worker_commit_missing = uncommitted and count == 0
        self.assertTrue(
            worker_commit_missing,
            "uncommitted=True AND commit_count=0 조합은 워커 commit 누락 신호여야 한다",
        )


if __name__ == "__main__":
    unittest.main()
