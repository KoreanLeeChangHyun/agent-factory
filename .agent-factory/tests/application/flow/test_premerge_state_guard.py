"""test premerge state guard.py - T-441 Reminder Status Guard Regression Test.

Verify the core quarter of W03 patch(` stage1 5 premerge state guard`).
W05 full-fledged revolving test adds 1~3 scenarios in a separate task,
This file is only for the W03 self sanity verification, which is only for the 1st quarter of the Hepper/guard.

Payment Terms:
  T1: feature branding absence → always block (force absence)
  T2: empty branch(commits ahead == 0) + force=False → block + clear error
  T3: Empty brand + force=True → Block + reflog fallback guide (Automatic trigger ban)
  T4: Changeable Brand (T-906 Top Route) → Pass
  T5: Helper  count commits ahead /  branch exists Module Verification
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

_ENGINE_DIR = str(Path(__file__).resolve().parents[3] / "engine")
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
        f"git   FIELD 0   failed:   FIELD 1   "
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
    """SetUp/tearDown +  git Patch Helper."""

    def setUp(self) -> None:
        self.repo = tempfile.mkdtemp(prefix="wf_test_t441_")
        _setup_repo_with_develop(self.repo)

    def tearDown(self) -> None:
        shutil.rmtree(self.repo, ignore_errors=True)

    def _patched_git(self, *args, repo_path=None):
        return _GuardTestBase._orig_git(*args, repo_path=self.repo)


_GuardTestBase._orig_git = _mp._git  # type: ignore[attr-defined]


class TestCountCommitsAhead(_GuardTestBase):
    """count commits ahead helfer unit validation."""

    def test_empty_branch_returns_zero(self) -> None:
        """Brands that don't change after quarterly in develop return 0."""
        _git_check(self.repo, "checkout", "-b", "feat/T-441-empty")
        with mock.patch.object(_mp, "_git", side_effect=self._patched_git):
            ahead = _mp._count_commits_ahead("feat/T-441-empty", base="develop")
        self.assertEqual(ahead, 0)

    def test_branch_with_commit_returns_positive(self) -> None:
        """The brand that has changed the positive return."""
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
        """Unexpected Brands Returns None."""
        with mock.patch.object(_mp, "_git", side_effect=self._patched_git):
            ahead = _mp._count_commits_ahead("feat/T-441-missing", base="develop")
        self.assertIsNone(ahead)


class TestBranchExists(_GuardTestBase):
    """branch exists helper unit verification."""

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
    """T1: feature branding absence → always blocked."""

    def test_branch_absent_force_false_blocks(self) -> None:
        with mock.patch(
            "flow.branch_strategy.get_feature_branch_for_ticket",
            return_value=None,
        ), mock.patch.object(_mp, "_git", side_effect=self._patched_git):
            ok, msg = _mp._stage1_5_premerge_state_guard(
                "T-441", worktree_path=None, force=False
            )
        self.assertFalse(ok)
        self.assertIn("Notice", msg)

    def test_branch_absent_force_true_blocks_with_advisory(self) -> None:
        with mock.patch(
            "flow.branch_strategy.get_feature_branch_for_ticket",
            return_value=None,
        ), mock.patch.object(_mp, "_git", side_effect=self._patched_git):
            ok, msg = _mp._stage1_5_premerge_state_guard(
                "T-441", worktree_path=None, force=True
            )
        # force even auto-pilgrim prohibition (User express consent canon)
        self.assertFalse(ok)


class TestPremergeGuardEmptyBranch(_GuardTestBase):
    """T2/T3: blank brand(commits ahead == 0) → block."""

    def setUp(self) -> None:
        super().setUp()
        # blank brand without changing the branch in develop
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
        # Auto Force Policy Prohibited Cannon — Force Rado Hollow Branding Block
        self.assertFalse(ok)
        self.assertIn("Empty branch detected", msg)


class TestPremergeGuardNormalPass(_GuardTestBase):
    """T4: Top (T-906 Top Route) → Pass."""

    def setUp(self) -> None:
        super().setUp()
        _git_check(self.repo, "checkout", "-b", "feat/T-441-normal")
        wf = os.path.join(self.repo, "work.py")
        with open(wf, "w") as f:
            f.write('x = "real"\n')
        _git_check(self.repo, "add", "work.py")
        _git_check(self.repo, "commit", "-m", "feat: real change")
        # Develop and manage quarterly status
        _git_check(self.repo, "checkout", "develop")

    def test_normal_branch_passes(self) -> None:
        with mock.patch(
            "flow.branch_strategy.get_feature_branch_for_ticket",
            return_value="feat/T-441-normal",
        ), mock.patch.object(_mp, "_git", side_effect=self._patched_git):
            ok, msg = _mp._stage1_5_premerge_state_guard(
                "T-441", worktree_path="/tmp/fake", force=False
            )
        self.assertTrue(ok, f"Normal Brand must pass (msg=   FIELD 0   )")
        self.assertEqual(msg, "")


if __name__ == "__main__":
    unittest.main()
