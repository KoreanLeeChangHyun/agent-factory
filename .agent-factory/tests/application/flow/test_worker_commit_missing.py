"""test worker commit missing.py - Watcher commit missing detection unit test (T-411 regression block)

Verify count feature branch commits and and conditional signals through 4 scenarios NEWS
  TC1: No commit to feature branding → count == 0
  TC2: 1 commit to the feature branch → count == 1
  TC3: Unexpected Brands → count == -1 (No Inspection)
  TC4: Untracked File + Commit 0 → AND Condition Signal Verification (T-411 Core Scenario)
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# sys.path: .agent-factory/engine enables flow package import
_ENGINE_DIR = str(Path(__file__).resolve().parents[3] / "engine")
if _ENGINE_DIR not in sys.path:
    sys.path.insert(0, _ENGINE_DIR)

from flow.worktree_manager import count_feature_branch_commits, has_uncommitted_changes


def _git(repo: str, *args: str) -> subprocess.CompletedProcess[str]:
    """execute git commands for temporary git repository."""
    return subprocess.run(
        ["git", "-C", repo] + list(args),
        capture_output=True,
        text=True,
    )


class TestWorkerCommitMissingDetection(unittest.TestCase):
    """count feature branch commits with has uncommitted changes and validation."""

    def setUp(self) -> None:
        """Create an isolated temporary git repository and branch the feature branch."""
        self.repo = tempfile.mkdtemp(prefix="wf_test_commit_missing_")
        # git init
        _git(self.repo, "init", "-b", "develop")
        # git config
        _git(self.repo, "config", "user.email", "test@example.com")
        _git(self.repo, "config", "user.name", "Test")
        # Create initial commits to develop brand
        init_file = os.path.join(self.repo, "README.md")
        with open(init_file, "w") as f:
            f.write("init\n")
        _git(self.repo, "add", "README.md")
        _git(self.repo, "commit", "-m", "init")
        # create a feature brand
        _git(self.repo, "checkout", "-b", "feat/T-999-test")

    def tearDown(self) -> None:
        shutil.rmtree(self.repo, ignore_errors=True)

    def test_count_zero_when_no_worker_commit(self) -> None:
        """TC1: Only untracked files without commit to feature branding → count == 0."""
        untracked = os.path.join(self.repo, "new_file.py")
        with open(untracked, "w") as f:
            f.write("# new\n")
        # see count only without add/commit
        count = count_feature_branch_commits(
            "feat/T-999-test", base_branch="develop", repo_path=self.repo
        )
        self.assertEqual(count, 0, "Commit-free feature brand must return 0")

    def test_count_positive_after_commit(self) -> None:
        """TC2: 1 commit to the feature branch → count == 1."""
        work_file = os.path.join(self.repo, "work.py")
        with open(work_file, "w") as f:
            f.write("x = 1\n")
        _git(self.repo, "add", "work.py")
        _git(self.repo, "commit", "-m", "feat: add work")
        count = count_feature_branch_commits(
            "feat/T-999-test", base_branch="develop", repo_path=self.repo
        )
        self.assertEqual(count, 1, "Commit One feature Brand must return 1")

    def test_count_negative_for_missing_branch(self) -> None:
        """TC3: Unexpected Brands → count == -1 (No inspection, no blocking)."""
        count = count_feature_branch_commits(
            "feat/T-000-missing", base_branch="develop", repo_path=self.repo
        )
        self.assertEqual(count, -1, "Brands that do not exist should return -1")

    def test_uncommitted_and_zero_commit_combo(self) -> None:
        """TC4: untracked file + commit 0 → AND conditional signal confirmation (T-411 core scenario).

        true and count feature branch commits == 0
        When meeting at the same time, the watcher commit missing signals occur.
        """
        untracked = os.path.join(self.repo, "worker_output.py")
        with open(untracked, "w") as f:
            f.write("# worker wrote this but forgot to commit\n")

        uncommitted = has_uncommitted_changes(self.repo)
        count = count_feature_branch_commits(
            "feat/T-999-test", base_branch="develop", repo_path=self.repo
        )

        self.assertTrue(uncommitted, "uncommitted=True")
        self.assertEqual(count, 0, "function brand without add/commit must be commit count=0")

        # AND Condition Verification — When both signals are met, Warker commit judges to be missing
        worker_commit_missing = uncommitted and count == 0
        self.assertTrue(
            worker_commit_missing,
            "uncommitted=True AND commit count=0 Combination should be missing Walker Commit",
        )


if __name__ == "__main__":
    unittest.main()
