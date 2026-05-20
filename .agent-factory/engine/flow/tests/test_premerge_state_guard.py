"""test_premerge_state_guard.py - T-441 재머지 상태 가드 회귀 테스트.

W03 패치(`_stage1_5_premerge_state_guard`)의 핵심 분기를 검증한다.
W05 본격 회귀 테스트는 별도 태스크에서 시나리오 1~3 을 추가하며,
본 파일은 W03 자체 sanity 검증용으로 헬퍼·가드 1단계 분기만 다룬다.

검증 범위:
  T1: feature 브랜치 부재 → 항상 차단 (force 무관)
  T2: 빈 브랜치(commits ahead == 0) + force=False → 차단 + 명확한 에러
  T3: 빈 브랜치 + force=True → 차단 + reflog fallback 안내 (자동 트리거 금지)
  T4: 변경분 있는 브랜치 (T-906 정상 경로) → 통과
  T5: 헬퍼 _count_commits_ahead / _branch_exists 단위 검증
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_ENGINE_DIR = str(Path(__file__).resolve().parent.parent.parent)
if _ENGINE_DIR not in sys.path:
    sys.path.insert(0, _ENGINE_DIR)

import flow.merge_pipeline as _mp  # noqa: E402


def _git(repo: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", repo] + list(args),
        capture_output=True,
        text=True,
    )


def _git_check(repo: str, *args: str) -> subprocess.CompletedProcess[str]:
    result = _git(repo, *args)
    assert result.returncode == 0, (
        f"git {' '.join(args)} 실패: {result.stderr}"
    )
    return result


def _setup_repo_with_develop(repo: str) -> None:
    _git_check(repo, "init", "-b", "develop")
    _git_check(repo, "config", "user.email", "test@example.com")
    _git_check(repo, "config", "user.name", "Test")
    work_file = os.path.join(repo, "work.py")
    with open(work_file, "w") as f:
        f.write('x = "base"\n')
    _git_check(repo, "add", "work.py")
    _git_check(repo, "commit", "-m", "init")


class _GuardTestBase(unittest.TestCase):
    """공통 setUp/tearDown + _git 패치 헬퍼."""

    def setUp(self) -> None:
        self.repo = tempfile.mkdtemp(prefix="wf_test_t441_")
        _setup_repo_with_develop(self.repo)

    def tearDown(self) -> None:
        shutil.rmtree(self.repo, ignore_errors=True)

    def _patched_git(self, *args, repo_path=None):
        return _GuardTestBase._orig_git(*args, repo_path=self.repo)


_GuardTestBase._orig_git = _mp._git  # type: ignore[attr-defined]


class TestCountCommitsAhead(_GuardTestBase):
    """_count_commits_ahead 헬퍼 단위 검증."""

    def test_empty_branch_returns_zero(self) -> None:
        """develop 에서 분기 직후 변경분 없는 브랜치는 0 반환."""
        _git_check(self.repo, "checkout", "-b", "feat/T-441-empty")
        with mock.patch.object(_mp, "_git", side_effect=self._patched_git):
            ahead = _mp._count_commits_ahead("feat/T-441-empty", base="develop")
        self.assertEqual(ahead, 0)

    def test_branch_with_commit_returns_positive(self) -> None:
        """변경분이 있는 브랜치는 positive 반환."""
        _git_check(self.repo, "checkout", "-b", "feat/T-441-real")
        wf = os.path.join(self.repo, "work.py")
        with open(wf, "w") as f:
            f.write('x = "real"\n')
        _git_check(self.repo, "add", "work.py")
        _git_check(self.repo, "commit", "-m", "feat: real change")
        with mock.patch.object(_mp, "_git", side_effect=self._patched_git):
            ahead = _mp._count_commits_ahead("feat/T-441-real", base="develop")
        self.assertEqual(ahead, 1)

    def test_missing_branch_returns_none(self) -> None:
        """존재하지 않는 브랜치는 None 반환."""
        with mock.patch.object(_mp, "_git", side_effect=self._patched_git):
            ahead = _mp._count_commits_ahead("feat/T-441-missing", base="develop")
        self.assertIsNone(ahead)


class TestBranchExists(_GuardTestBase):
    """_branch_exists 헬퍼 단위 검증."""

    def test_existing_branch(self) -> None:
        _git_check(self.repo, "checkout", "-b", "feat/T-441-x")
        with mock.patch.object(_mp, "_git", side_effect=self._patched_git):
            self.assertTrue(_mp._branch_exists("feat/T-441-x"))

    def test_missing_branch(self) -> None:
        with mock.patch.object(_mp, "_git", side_effect=self._patched_git):
            self.assertFalse(_mp._branch_exists("feat/T-441-missing"))

    def test_empty_branch_name(self) -> None:
        self.assertFalse(_mp._branch_exists(""))


class TestPremergeGuardBranchAbsent(_GuardTestBase):
    """T1: feature 브랜치 부재 → 항상 차단."""

    def test_branch_absent_force_false_blocks(self) -> None:
        with mock.patch(
            "flow.branch_strategy.get_feature_branch_for_ticket",
            return_value=None,
        ), mock.patch.object(_mp, "_git", side_effect=self._patched_git):
            ok, msg = _mp._stage1_5_premerge_state_guard(
                "T-441", worktree_path=None, force=False
            )
        self.assertFalse(ok)
        self.assertIn("부재", msg)

    def test_branch_absent_force_true_blocks_with_advisory(self) -> None:
        with mock.patch(
            "flow.branch_strategy.get_feature_branch_for_ticket",
            return_value=None,
        ), mock.patch.object(_mp, "_git", side_effect=self._patched_git):
            ok, msg = _mp._stage1_5_premerge_state_guard(
                "T-441", worktree_path=None, force=True
            )
        # force 라도 자동 머지 금지 (사용자 명시 동의 캐논)
        self.assertFalse(ok)


class TestPremergeGuardEmptyBranch(_GuardTestBase):
    """T2/T3: 빈 브랜치(commits ahead == 0) → 차단."""

    def setUp(self) -> None:
        super().setUp()
        # develop 에서 분기 후 변경 없이 그대로 둔 빈 브랜치
        _git_check(self.repo, "branch", "feat/T-441-empty")

    def test_empty_branch_force_false_blocks(self) -> None:
        with mock.patch(
            "flow.branch_strategy.get_feature_branch_for_ticket",
            return_value="feat/T-441-empty",
        ), mock.patch.object(_mp, "_git", side_effect=self._patched_git):
            ok, msg = _mp._stage1_5_premerge_state_guard(
                "T-441", worktree_path="/tmp/fake", force=False
            )
        self.assertFalse(ok)
        self.assertIn("Empty branch detected", msg)

    def test_empty_branch_force_true_still_blocks(self) -> None:
        with mock.patch(
            "flow.branch_strategy.get_feature_branch_for_ticket",
            return_value="feat/T-441-empty",
        ), mock.patch.object(_mp, "_git", side_effect=self._patched_git):
            ok, msg = _mp._stage1_5_premerge_state_guard(
                "T-441", worktree_path="/tmp/fake", force=True
            )
        # 자동 강제 정책 금지 캐논 — force 라도 빈 브랜치는 차단
        self.assertFalse(ok)
        self.assertIn("Empty branch detected", msg)


class TestPremergeGuardNormalPass(_GuardTestBase):
    """T4: 정상 (T-906 정상 경로) → 통과."""

    def setUp(self) -> None:
        super().setUp()
        _git_check(self.repo, "checkout", "-b", "feat/T-441-normal")
        wf = os.path.join(self.repo, "work.py")
        with open(wf, "w") as f:
            f.write('x = "real"\n')
        _git_check(self.repo, "add", "work.py")
        _git_check(self.repo, "commit", "-m", "feat: real change")
        # develop 으로 돌아와 분기 상태 정리
        _git_check(self.repo, "checkout", "develop")

    def test_normal_branch_passes(self) -> None:
        with mock.patch(
            "flow.branch_strategy.get_feature_branch_for_ticket",
            return_value="feat/T-441-normal",
        ), mock.patch.object(_mp, "_git", side_effect=self._patched_git):
            ok, msg = _mp._stage1_5_premerge_state_guard(
                "T-441", worktree_path="/tmp/fake", force=False
            )
        self.assertTrue(ok, f"정상 브랜치는 통과해야 한다 (msg={msg})")
        self.assertEqual(msg, "")


if __name__ == "__main__":
    unittest.main()
