"""test merge conflict detection.py - Enhanced merge collision detection (WR-907) unit testing.

Payment Terms:
  T1:  detect conflicts — diff --diff-filter=U is the default path to return crash files
  git status --porcelain fallback
  T3:  detect conflicts — return sentinel when both git calls fail
  T4: cmd complete — conflicts=[] + error message conflict pattern → SystemExit(1)
  T5: cmd complete — Normal success path is completed without SystemExit (Return Guard)
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

# sys.path: .agent-factory/engine enables flow package import
_ENGINE_DIR = str(Path(__file__).resolve().parents[3] / "engine")
if _ENGINE_DIR not in sys.path:
    sys.path.insert(0, _ENGINE_DIR)

from flow import worktree_manager  # noqa: E402
from flow.worktree_manager import (  # noqa: E402
    _detect_conflicts,
    _parse_porcelain_conflicts,
    _SENTINEL_UNKNOWN_CONFLICT,
)


# ───────────────────────────────────────────────


def _git(repo: str, *args: str) -> subprocess.CompletedProcess[str]:
    """execute git commands for temporary git repository."""
    return subprocess.run(
        ["git", "-C", repo] + list(args),
        capture_output=True,
        text=True,
    )


def _git_check(repo: str, *args: str) -> subprocess.CompletedProcess[str]:
    """execute git command and throw AssertionError when failed."""
    result = _git(repo, *args)
    assert result.returncode == 0, (
        f"git   FIELD 0   failed:   FIELD 1   "
    )
    return result


def _setup_conflict_repo(repo: str) -> str:
    """develop + feature construct a temporary repo that occurred the same line collision in the brand.

    - Development: change the first line of work.py to 'x = "develop"\n' + commit
    - Feature: Change the same line to 'x = "feature"\n' + commit
    - git merge feature in development (No conflict, not resolve)

    Returns:
        feature Brand Name.
    """
    _git_check(repo, "init", "-b", "develop")
    _git_check(repo, "config", "user.email", "test@example.com")
    _git_check(repo, "config", "user.name", "Test")

    work_file = os.path.join(repo, "work.py")
    with open(work_file, "w") as f:
        f.write('x = "base"\n')
    _git_check(repo, "add", "work.py")
    _git_check(repo, "commit", "-m", "init")

    # feature Brand: same line fix
    feature_branch = "feat/WR-907-test"
    _git_check(repo, "checkout", "-b", feature_branch)
    with open(work_file, "w") as f:
        f.write('x = "feature"\n')
    _git_check(repo, "add", "work.py")
    _git_check(repo, "commit", "-m", "feat: change x")

    # Fix the same line to develop
    _git_check(repo, "checkout", "develop")
    with open(work_file, "w") as f:
        f.write('x = "develop"\n')
    _git_check(repo, "add", "work.py")
    _git_check(repo, "commit", "-m", "develop: change x")

    # merge attempt — a collision (unlimited returncode is ignored)
    subprocess.run(
        ["git", "-C", repo, "merge", "--no-ff", feature_branch],
        capture_output=True,
        text=True,
    )

    return feature_branch


# ────────────────────────────────────────────────


class TestDetectConflictsDiffFilterPopulates(unittest.TestCase):
    """detect conflicts returns the crash file from diff --diff-filter=U."""

    def setUp(self) -> None:
        self.repo = tempfile.mkdtemp(prefix="wf_test_t907_conflict_")
        _setup_conflict_repo(self.repo)

    def tearDown(self) -> None:
        shutil.rmtree(self.repo, ignore_errors=True)

    def test_detect_conflicts_diff_filter_populates(self) -> None:
        """detect conflicts returns a crash file after collision from temporary repo."""
        conflicts = _detect_conflicts(repo_path=self.repo)
        # sentinel should not be included, and work.py should be included
        self.assertNotIn(_SENTINEL_UNKNOWN_CONFLICT, conflicts)
        self.assertIn("work.py", conflicts)


# ─── T2: _detect_conflicts porcelain fallback ────────────────────────────────


class TestDetectConflictsPorcelainFallback(unittest.TestCase):
    """1st(diff --diff-filter=U) returns a crash file to porcelain fallback when the result is empty."""

    def _make_completed(
        self, returncode: int, stdout: str
    ) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(
            args=[], returncode=returncode, stdout=stdout, stderr=""
        )

    def test_detect_conflicts_porcelain_fallback(self) -> None:
        """diff filter returns the crash file as porcelain result when empty stdout return."""
        call_count = 0

        def fake_git(*args: str, repo_path=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # 1st: diff --name-only --diff-filter=U → empty result
                return self._make_completed(0, "")
            else:
                # 2nd: status --porcelain → UU code included
                return self._make_completed(0, "UU work.py\n")

        with mock.patch.object(worktree_manager, "_git", side_effect=fake_git):
            conflicts = _detect_conflicts()

        self.assertEqual(conflicts, ["work.py"])


# ─── T3: _detect_conflicts sentinel on both failure ──────────────────────────


class TestDetectConflictsSentinelOnFailure(unittest.TestCase):
    """Both git calls return sentinel if failed (returncode != 0)."""

    def _make_failed(self) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="fatal: not a git repo"
        )

    def test_detect_conflicts_sentinel_on_failure(self) -> None:
        """['<unknown-conflict>'] sentinel return when both call failed."""
        with mock.patch.object(worktree_manager, "_git", return_value=self._make_failed()):
            conflicts = _detect_conflicts()

        self.assertEqual(conflicts, [_SENTINEL_UNKNOWN_CONFLICT])


# ─ T4: cmd complete — empty conflicts + error message crash patterns → SystemExit ───────


class TestCmdCompleteExitsOnEmptyConflictsWithSignalMessage(unittest.TestCase):
    """merge result.success=False + conflicts=[] + error message
    cmd complete generates SystemExit(1).
    """

    def test_cmd_complete_exits_on_empty_conflicts_with_signal_message(self) -> None:
        """systemExit if the crash pattern in error message is empty."""
        from flow import conveyor_cli
        from flow.worktree_manager import MergeResult

        # merge to develop This crash fails to return monkeypatch
        fake_merge_result = MergeResult(
            success=False,
            merge_commit="",
            merged_branch="feat/WR-907-test",
            conflicts=[],
            error_message="Merged Collision: Collision detected in work.py",
        )

        with mock.patch.object(
            conveyor_cli, "find_work_request_file", return_value="/tmp/fake/WR-907.xml"
        ), mock.patch(
            "flow.worktree_manager.is_worktree_enabled", return_value=True
        ), mock.patch(
            "flow.worktree_manager.get_worktree_path", return_value="/tmp/fake-worktree"
        ), mock.patch(
            "flow.worktree_manager.has_uncommitted_changes", return_value=False
        ), mock.patch(
            "flow.worktree_manager.merge_to_develop", return_value=fake_merge_result
        ), mock.patch(
            "flow.branch_strategy.get_feature_branch_for_work_request",
            return_value="feat/WR-907-test",
        ):
            with self.assertRaises(SystemExit) as ctx:
                conveyor_cli.cmd_complete("WR-907")

        self.assertEqual(ctx.exception.code, 1)


# ─ T5: cmd complete — Normal success path completed without SystemExit (Return Guard) ────────


class TestCmdCompleteProceedsOnSuccess(unittest.TestCase):
    """merge to develop When successful cmd complete completes Complete transformation without SystemExit."""

    def setUp(self) -> None:
        # Create a temporary WorkRequest file in a temporary directory
        self.tmp_dir = tempfile.mkdtemp(prefix="wf_test_t907_complete_success_")
        self.complete_dir = os.path.join(self.tmp_dir, "complete")
        self.verifying_dir = os.path.join(self.tmp_dir, "verifying")
        os.makedirs(self.verifying_dir, exist_ok=True)
        os.makedirs(self.complete_dir, exist_ok=True)

        # Verifying status WorkRequest XML creation
        self.work_request_number = "WR-907"
        self.work_request_file = os.path.join(self.verifying_dir, f"{self.work_request_number}.xml")
        with open(self.work_request_file, "w", encoding="utf-8") as f:
            f.write(
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                "<work_request>\n"
                "  <metadata>\n"
                f"    <number>{self.work_request_number}</number>\n"
                "    <title>test WorkRequest</title>\n"
                "    <created>2026-05-07 12:00:00</created>\n"
                "    <updated>2026-05-07 12:00:00</updated>\n"
                "    <status>Verifying</status>\n"
                "    <command>implement</command>\n"
                "  </metadata>\n"
                "  <prompt />\n"
                "  <result />\n"
                "</work_request>\n"
            )

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_cmd_complete_proceeds_on_success(self) -> None:
        """merge to develop success returns when cmd complete completes Complete transition."""
        from flow import conveyor_cli
        from flow import work_request_repository
        from flow.worktree_manager import MergeResult

        fake_merge_result = MergeResult(
            success=True,
            merge_commit="abc12345def67890",
            merged_branch="feat/WR-907-test",
            conflicts=[],
            error_message="",
        )

        patched_status_map = dict(work_request_repository.STATUS_DIR_MAP)
        patched_status_map["Verifying"] = self.verifying_dir
        patched_status_map["Complete"] = self.complete_dir

        with mock.patch.object(
            work_request_repository, "STATUS_DIR_MAP", patched_status_map
        ), mock.patch.object(
            work_request_repository, "CONVEYOR_VERIFYING_DIR", self.verifying_dir
        ), mock.patch.object(
            work_request_repository, "CONVEYOR_COMPLETE_DIR", self.complete_dir
        ), mock.patch.object(
            conveyor_cli, "find_work_request_file", return_value=self.work_request_file
        ), mock.patch(
            "flow.worktree_manager.is_worktree_enabled", return_value=True
        ), mock.patch(
            "flow.worktree_manager.get_worktree_path", return_value="/tmp/fake-worktree"
        ), mock.patch(
            "flow.worktree_manager.has_uncommitted_changes", return_value=False
        ), mock.patch(
            "flow.worktree_manager.merge_to_develop", return_value=fake_merge_result
        ), mock.patch(
            "flow.branch_strategy.get_feature_branch_for_work_request",
            return_value="feat/WR-907-test",
        ), mock.patch.object(
            conveyor_cli, "update_result", return_value=None
        ):
            # SystemExit must be completed
            try:
                conveyor_cli.cmd_complete(self.work_request_number)
            except SystemExit as e:
                self.fail(f"cmd complete caused unexpected SystemExit({e.code})")


if __name__ == "__main__":
    unittest.main()
