"""test_undo_redo_cycle.py - WR-441 Complete Rollback + Jammerge integrated regression test.

W05 Full-scale integrated regression test. Unit guard added by W03 (`_stage1_5_premerge_state_guard`)
Verify within a larger cycle (Complete rollback → Worktree regeneration → Remerge).

Regression block (WR-440 example, 2026-05-08):
  1. flow-merge feat/WR-440 to develop normal merge (51555f3)
  2. undo_complete.py:_strategy_reset resets develop to 51555f3^ (= ba74608)
  3. Work tree/feature branch was recreated, but no changes were made (empty branch)
  4. A separate revert commit (6efc6ef) was added above develop.
  5. Attempt to remerge with flow-merge --force → anchor verification failed
  6. _handle_anchor_failure reset --hard pre_merge_develop_sha (= 6efc6ef)
     Execute → Revert commit does not disappear together, but changes are lost.
  7. Manual recovery by user as a74fb7a

This test simulates each branch of the above cycle within an isolated temporary git repo.
All cases blocked/passed by the W03 guard are grouped with regression 0.

Verification Scenario:
  S1 (normal path / WR-906): force unchecked + work tree/branch with changes
      → Stage 1.5 guard passed + Stage 2.5 anchor verification passed
      → develop HEAD = merge commit
  S2 (force + absence / guidance information): force check + work tree/branch absence
      → Guard blocking + reflog fallback information message exposed (automatically applied
      → develop HEAD change 0
  S3 (voice / general): force not checked + work tree/branch absent
      → Guard blocking + clear error message
      → 0 empty merges, 0 develop HEAD changes
  S4 (WR-905 normal): reset simulation before undo_complete push
      → develop HEAD = merge_commit^ (no commit loss 0)
  S5 (WR-906 normal follow-up): Remerge after committing changes to the work tree
      → develop HEAD integration (merge commit + preserve ahead commits)
  S6 (WR-440 regression blocking advisory): Attempting to merge an empty branch above a separate commit
      → Stage 1.5 guard blocking (blocked before reaching the anchor stage)
      Also, when calling `_handle_anchor_failure` directly, parent1_mismatch advisory is triggered.

The test is based on unittest, using the existing `test_premerge_state_guard.py`,
Maintain consistency with the  pattern in `test_merge_anchor_safety.py`.
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

# sys.path: Enable flow package import by including .agent-factory/engine
_ENGINE_DIR = str(Path(__file__).resolve().parents[3] / "engine")
if _ENGINE_DIR not in sys.path:
    sys.path.insert(0, _ENGINE_DIR)

import flow.merge_pipeline as _mp  # noqa: E402


# ─── git helper ────────────────────────────────────────────────────────────────────


def _git(repo: str, *args: str) -> subprocess.CompletedProcess[str]:
    """Execute the git command targeting the temporary git repository."""
    return subprocess.run(
        ["git", "-C", repo] + list(args),
        capture_output=True,
        text=True,
    )


def _git_check(repo: str, *args: str) -> subprocess.CompletedProcess[str]:
    """Executes the git command and throws AssertionError on failure."""
    result = _git(repo, *args)
    assert result.returncode == 0, (
        f"git {' '.join(args)} failed: {result.stderr}"
    )
    return result


def _setup_base_repo(repo: str) -> None:
    """Initialize a common base repo: init + user config + base commit on develop."""
    _git_check(repo, "init", "-b", "develop")
    _git_check(repo, "config", "user.email", "test@example.com")
    _git_check(repo, "config", "user.name", "Test")

    work_file = os.path.join(repo, "work.py")
    with open(work_file, "w") as f:
        f.write('x = "base"\n')
    _git_check(repo, "add", "work.py")
    _git_check(repo, "commit", "-m", "init")


def _head_sha(repo: str, ref: str = "HEAD") -> str:
    """Returns the SHA pointed to by ref."""
    result = _git_check(repo, "rev-parse", ref)
    return result.stdout.strip()


def _log_shas(repo: str, n: int = 20) -> list[str]:
    """develop log SHA list (newest first)."""
    result = _git_check(repo, "log", "--format=%H", f"-{n}")
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _commit_on(repo: str, branch: str, filename: str, content: str, msg: str) -> str:
    """SHA is returned after committing the file on the branch. If branch does not exist, create a branch."""
    # Check current branch
    cur = _git_check(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    if cur != branch:
        # Check if branch exists
        exists = _git(repo, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}")
        if exists.returncode == 0:
            _git_check(repo, "checkout", branch)
        else:
            _git_check(repo, "checkout", "-b", branch)
    fpath = os.path.join(repo, filename)
    with open(fpath, "w") as f:
        f.write(content)
    _git_check(repo, "add", filename)
    _git_check(repo, "commit", "-m", msg)
    return _head_sha(repo)


# ─── Common Base ────────────────────────────────────────────────────────────────


class _CycleTestBase(unittest.TestCase):
    """Common setUp/tearDown for all cycle scenarios.

    Each test creates a develop + feat/WR-441-* branch in an isolated temporary git repo.
    Create a patched_git  that routes _mp._git calls to the temporary repo.
    Provides.
    """

    work_request: str = "WR-441"
    feature_branch: str = "feat/WR-441-cycle"

    def setUp(self) -> None:
        self.repo = tempfile.mkdtemp(prefix="wf_test_t441_cycle_")
        _setup_base_repo(self.repo)
        self.develop_base_sha = _head_sha(self.repo, "develop")

    def tearDown(self) -> None:
        shutil.rmtree(self.repo, ignore_errors=True)

    # ── helpers ─────────────────────────────────────────────────────────────

    def _patched_git(self):
        orig = _mp._git

        def _wrapper(*args, repo_path=None):
            return orig(*args, repo_path=self.repo)

        return _wrapper

    def _make_feature_with_change(
        self, branch: str | None = None, filename: str = "feat.py", content: str = 'feat = 1\n'
    ) -> str:
        """After the develop branch, commit one change to the feature branch. SHA return."""
        target = branch or self.feature_branch
        _git_check(self.repo, "checkout", "develop")
        _git_check(self.repo, "checkout", "-b", target)
        feat_path = os.path.join(self.repo, filename)
        with open(feat_path, "w") as f:
            f.write(content)
        _git_check(self.repo, "add", filename)
        _git_check(self.repo, "commit", "-m", f"feat({self.work_request}): add {filename}")
        sha = _head_sha(self.repo)
        _git_check(self.repo, "checkout", "develop")
        return sha

    def _make_empty_feature(self, branch: str | None = None) -> None:
        """Create only a feature branch without changes immediately after the develop branch (WR-440 regression simulation)."""
        target = branch or self.feature_branch
        _git_check(self.repo, "branch", target, "develop")

    def _add_unrelated_commit_on_develop(
        self, filename: str = "unrelated.py", content: str = "u = 1\n"
    ) -> str:
        """After adding a separate commit above develop, SHA is returned (6efc6ef simulation of WR-440)."""
        _git_check(self.repo, "checkout", "develop")
        fpath = os.path.join(self.repo, filename)
        with open(fpath, "w") as f:
            f.write(content)
        _git_check(self.repo, "add", filename)
        _git_check(self.repo, "commit", "-m", "chore: unrelated revert-style commit")
        return _head_sha(self.repo)

    def _non_ff_merge(self, branch: str | None = None) -> str:
        """After checking out with develop, merge the branch with --no-ff. merge commit returns SHA."""
        target = branch or self.feature_branch
        _git_check(self.repo, "checkout", "develop")
        _git_check(
            self.repo,
            "merge",
            "--no-ff",
            "-m",
            f"Merge {target} into develop",
            target,
        )
        return _head_sha(self.repo)


# ─── S1: Normal path (force unchecked + work tree/branch with changes) ──────────────


class TestScenario1NormalPath(_CycleTestBase):
    """S1 — Normal Path (WR-906 Verifying→Complete DnD equivalent).

    verification:
      - Pass Stage 1.5 guard (commits ahead > 0)
      - Pass anchor verification after non-ff merge
      - develop HEAD == merge commit
    """

    def test_normal_merge_passes_guard_and_anchor(self) -> None:
        feature_sha = self._make_feature_with_change()
        pre_merge_sha = _head_sha(self.repo, "develop")

        # Stage 1.5 Guard Pass Verification
        with mock.patch(
            "flow.branch_strategy.get_feature_branch_for_work_request",
            return_value=self.feature_branch,
        ), mock.patch.object(_mp, "_git", side_effect=self._patched_git()):
            ok, msg = _mp._stage1_5_premerge_state_guard(
                self.work_request, worktree_path=self.repo, force=False
            )
        self.assertTrue(ok, f"S1 guard must be passed (msg= {msg} )")
        self.assertEqual(msg, "")

        # Anchor verification passed after non-ff merge
        merge_commit = self._non_ff_merge()

        with mock.patch(
            "flow.worktree_manager.is_worktree_enabled", return_value=True
        ), mock.patch.object(_mp, "_git", side_effect=self._patched_git()):
            anchor_ok = _mp._stage2_5_verify_merge_anchor(
                merge_commit=merge_commit,
                feature_branch=self.feature_branch,
                dry_run=False,
                pre_merge_develop_sha=pre_merge_sha,
            )
        self.assertTrue(anchor_ok, "S1 anchor verification must pass")

        # develop HEAD = merge commit (no change)
        self.assertEqual(
            _head_sha(self.repo, "develop"),
            merge_commit,
            "After S1 normal merge, develop HEAD must be merge commit",
        )

        # Feature branch changes can reach develop log
        log = _log_shas(self.repo, n=10)
        self.assertIn(feature_sha, log, "Feature commits should be kept in develop")


# ─── S2: force + absence of work tree/branch (advisory information) ──────────────────────────


class TestScenario2ForceAbsentReflogAdvisory(_CycleTestBase):
    """S2 — force=True + absence of worktree/branch.

    Regression blocking: In the WR-440 case, when the user attempts to remerge with an empty work tree or branch.
    If the guard does not block, empty merge + reset --hard will result in loss due to separate commit location.
    W03 policy: Prohibit automatic triggering even if force=True + only expose reflog fallback notification.

    verification:
      - Guard blocking (returns False) + guidance message exposure
      - develop HEAD change 0
    """

    def test_force_with_branch_absent_blocks_with_advisory(self) -> None:
        pre_merge_sha = _head_sha(self.repo, "develop")

        captured_stderr: list[str] = []

        def fake_print(*args, **kwargs):
            if kwargs.get("file") is sys.stderr:
                captured_stderr.append(" ".join(str(a) for a in args))

        with mock.patch(
            "flow.branch_strategy.get_feature_branch_for_work_request",
            return_value=None,  # branch unresolved
        ), mock.patch.object(
            _mp, "_git", side_effect=self._patched_git()
        ), mock.patch("builtins.print", side_effect=fake_print):
            ok, msg = _mp._stage1_5_premerge_state_guard(
                self.work_request, worktree_path=None, force=True
            )

        self.assertFalse(ok, "Even with force, branch members must be blocked.")
        self.assertIn("absence", msg)

        # Advisory message exposure (reflog guide keyword)
        all_stderr = "\n".join(captured_stderr)
        self.assertIn(
            "reflog",
            all_stderr.lower(),
            "In force mode, reflog fallback information should be exposed.",
        )

        # develop HEAD change 0 (disable reset/merge automatic trigger)
        self.assertEqual(
            _head_sha(self.repo, "develop"),
            pre_merge_sha,
            "develop HEAD should not be changed when S2 guard is blocked",
        )


# ─── S3: Voice (force not checked + absence) ──────────────────────────────────────────────


class TestScenario3NormalAbsentBlocked(_CycleTestBase):
    """S3 — Negative scenario (force unchecked + work tree/branch absent).

    verification:
      - Guard blocking + clear error message
      - 0 empty merges / develop HEAD change 0
    """

    def test_no_force_with_branch_absent_blocks_clearly(self) -> None:
        pre_merge_sha = _head_sha(self.repo, "develop")
        log_shas_before = _log_shas(self.repo, n=20)

        error_messages: list[str] = []

        def fake_error(msg: str) -> None:
            error_messages.append(msg)

        with mock.patch(
            "flow.branch_strategy.get_feature_branch_for_work_request",
            return_value=None,
        ), mock.patch.object(
            _mp, "_git", side_effect=self._patched_git()
        ), mock.patch.object(_mp, "_error", side_effect=fake_error):
            ok, msg = _mp._stage1_5_premerge_state_guard(
                self.work_request, worktree_path=None, force=False
            )

        self.assertFalse(ok, "force unchecked + members must be blocked")
        self.assertIn("absence", msg)

        # Verify that a clear error message is issued
        all_errors = "\n".join(error_messages)
        self.assertIn("[GUARD]", all_errors, "Guard identifier must be included in error")

        # develop HEAD change 0
        self.assertEqual(
            _head_sha(self.repo, "develop"),
            pre_merge_sha,
            "develop HEAD should not be changed when S3 guard is blocked",
        )

        # 0 empty merges — develop logs must be the same
        self.assertEqual(
            _log_shas(self.repo, n=20),
            log_shas_before,
            "When S3 guard is blocked, new commits should not be added to the develop log.",
        )

    def test_no_force_with_empty_branch_blocks(self) -> None:
        """Also block empty branches that exist but have zero changes (WR-440 regression core)."""
        self._make_empty_feature()
        pre_merge_sha = _head_sha(self.repo, "develop")

        with mock.patch(
            "flow.branch_strategy.get_feature_branch_for_work_request",
            return_value=self.feature_branch,
        ), mock.patch.object(_mp, "_git", side_effect=self._patched_git()):
            ok, msg = _mp._stage1_5_premerge_state_guard(
                self.work_request, worktree_path=self.repo, force=False
            )

        self.assertFalse(ok, "Empty branches should be blocked")
        self.assertIn("Empty branch detected", msg)

        # develop HEAD change 0
        self.assertEqual(
            _head_sha(self.repo, "develop"),
            pre_merge_sha,
            "develop HEAD should not be changed when an empty branch is blocked",
        )


# ─── S4: WR-905 normal path (reset before push --hard merge_commit^) ──────────────────


class TestScenario4UndoCompleteResetPreservesUnrelated(_CycleTestBase):
    """S4 — reset strategy before undo_complete push (equivalent behavior to `_strategy_reset`).

    Regression blocking: `git reset --hard <merge_commit>^` in undo_complete.py:396
    Verify that the separate commit loss is 0.

    scenario:
      1. Add separate ahead commit (a1) to develop
      2. Branch feature branch + commit
      3. Return to develop and merge non-ff → merge_commit (M1)
      4. Simulate undo_complete reset: `git reset --hard M1^`
      5. develop HEAD == M1^ == a1 (preserve commit separately)
    """

    def test_undo_complete_reset_preserves_unrelated_ahead_commit(self) -> None:
        # 1. Develop ahead commit
        a1_sha = self._add_unrelated_commit_on_develop(
            filename="ahead1.py", content="a1 = 1\n"
        )

        # 2-3. feature branch + commit + non-ff merge
        feature_sha = self._make_feature_with_change()
        merge_commit = self._non_ff_merge()
        # M1^ == a1 (immediately before develop HEAD)
        m1_parent1 = _head_sha(self.repo, f"{merge_commit}^1")
        self.assertEqual(
            m1_parent1, a1_sha, "M1^1 must be ahead commit"
        )

        # 4. undo_complete reset simulation
        _git_check(self.repo, "reset", "--hard", f"{merge_commit}^")

        # 5. develop HEAD == a1 (preserve separate commits, exclude feature commits)
        head_after = _head_sha(self.repo, "develop")
        self.assertEqual(
            head_after,
            a1_sha,
            "After WR-905 reset, develop HEAD must be ahead commit.",
        )

        # Feature commits should be excluded from develop log
        log = _log_shas(self.repo, n=20)
        self.assertNotIn(
            feature_sha,
            log,
            "After WR-905 reset, feature commits should not be in the develop log.",
        )
        # Regardless, the commit ahead should be preserved.
        self.assertIn(
            a1_sha,
            log,
            "After WR-905 reset, ahead commits must be preserved in develop.",
        )


# ─── S5: WR-906 normal path (Verifying → Complete DnD follow-up — Worktree commit + remerge) ──


class TestScenario5RemergeAfterFreshCommit(_CycleTestBase):
    """S5 — Complete After rollback, commit changes back to the work tree + remerge.

    Recurrence 0 circuit: When the user re-commits the work to the work tree after undo_complete
    Feature branch's commits ahead > 0, passing Stage 1.5 guard + anchor
    Verification passed → develop HEAD = normal merge commit.

    scenario:
      1. Feature branch empty state (simulated right after undo_complete)
      2. Commit one change to the work tree (feature branch on temporary repo)
      3. Pass guard + non-ff merge + pass anchor verification
      4. develop HEAD = normal merge commit
    """

    def test_remerge_after_fresh_commit_succeeds(self) -> None:
        # 1. Empty feature branch (simulated right after undo_complete)
        self._make_empty_feature()
        pre_merge_sha = _head_sha(self.repo, "develop")

        # 1-1. In an empty state, the guard should block (the regression guard itself)
        with mock.patch(
            "flow.branch_strategy.get_feature_branch_for_work_request",
            return_value=self.feature_branch,
        ), mock.patch.object(_mp, "_git", side_effect=self._patched_git()):
            ok_empty, _ = _mp._stage1_5_premerge_state_guard(
                self.work_request, worktree_path=self.repo, force=False
            )
        self.assertFalse(
            ok_empty, "The guard should block in the empty feature branch state."
        )

        # 2. Commit one change to the work tree
        _git_check(self.repo, "checkout", self.feature_branch)
        feat_path = os.path.join(self.repo, "feat.py")
        with open(feat_path, "w") as f:
            f.write("feat = 'remerge-success'\n")
        _git_check(self.repo, "add", "feat.py")
        _git_check(self.repo, "commit", "-m", f"feat({self.work_request}): re-add change")
        feature_sha = _head_sha(self.repo)
        _git_check(self.repo, "checkout", "develop")

        # 3. Pass the guard
        with mock.patch(
            "flow.branch_strategy.get_feature_branch_for_work_request",
            return_value=self.feature_branch,
        ), mock.patch.object(_mp, "_git", side_effect=self._patched_git()):
            ok, msg = _mp._stage1_5_premerge_state_guard(
                self.work_request, worktree_path=self.repo, force=False
            )
        self.assertTrue(
            ok, f"After committing the change, the guard must pass (msg= {msg} )"
        )

        # 3-1. Non-ff merge + anchor verification passed
        merge_commit = self._non_ff_merge()
        with mock.patch(
            "flow.worktree_manager.is_worktree_enabled", return_value=True
        ), mock.patch.object(_mp, "_git", side_effect=self._patched_git()):
            anchor_ok = _mp._stage2_5_verify_merge_anchor(
                merge_commit=merge_commit,
                feature_branch=self.feature_branch,
                dry_run=False,
                pre_merge_develop_sha=pre_merge_sha,
            )
        self.assertTrue(anchor_ok, "Jammerge anchor verification must pass")

        # 4. Develop HEAD matching + feature commit preservation
        self.assertEqual(_head_sha(self.repo, "develop"), merge_commit)
        log = _log_shas(self.repo, n=20)
        self.assertIn(feature_sha, log, "Feature commits must be preserved after remerging")


# ─── S6: WR-440 regression blocking + parent1_mismatch advisory ──────────────────────────


class TestScenario6T440RegressionBlocked(_CycleTestBase):
    """S6 — Block WR-440 regression scenario (Stage 1.5) + trigger advisory.

    Regression block (WR-440 example, 2026-05-08):
      - Immediately after undo_complete, revert anything above develop in an empty worktree/branch state
        commit added
      - flow-merge attempts to merge an empty branch above it → anchor fails →
        `_handle_anchor_failure` reset --hard pre_merge_develop_sha (=
        commit) run
      - Two guards of W03 must operate simultaneously:
        (1) Stage 1.5: Blocking the empty branch itself (first line of defense)
        (2) parent1_mismatch advisory of `_handle_anchor_failure`:
            If you reach the anchor stage through a detour, reset_target ≠
            When merge_commit^1, warn the user of the possibility of losing a separate commit.
            (advisory only, does not block reset — automatic enforcement policy ban canon)
    """

    def test_empty_branch_on_unrelated_develop_blocked_at_stage1_5(self) -> None:
        """First line of defense: Guard blocking in develop with empty branches + separate commits added."""
        # WR-440 sequence reproduction
        self._add_unrelated_commit_on_develop(
            filename="revert.py", content="r = 1\n"
        )  # Special thing revert commit (6efc6ef simulation)
        self._make_empty_feature()  # Empty branch (simulated right after regenerating undo_complete)
        pre_state_log = _log_shas(self.repo, n=20)
        pre_state_head = _head_sha(self.repo, "develop")

        with mock.patch(
            "flow.branch_strategy.get_feature_branch_for_work_request",
            return_value=self.feature_branch,
        ), mock.patch.object(_mp, "_git", side_effect=self._patched_git()):
            ok, msg = _mp._stage1_5_premerge_state_guard(
                self.work_request, worktree_path=self.repo, force=False
            )

        self.assertFalse(ok, "WR-440 regression scenario should be blocked at Stage 1.5")
        self.assertIn("Empty branch detected", msg)

        # develop HEAD / log change 0 — empty merge + reset both should not occur
        self.assertEqual(
            _head_sha(self.repo, "develop"),
            pre_state_head,
            "When WR-440 is blocked, develop HEAD must not be changed (separate commits are preserved)",
        )
        self.assertEqual(
            _log_shas(self.repo, n=20),
            pre_state_log,
            "Develop log should not be changed when WR-440 is blocked.",
        )

    def test_handle_anchor_failure_parent1_mismatch_advisory(self) -> None:
        """Second line of defense: reset_target ≠ merge_commit^1 advisory when anchor fails.

        advisory only — reset itself does not block and alerts users to suspicious cases.
        Warn explicitly. Canon compliance prohibits introduction of automatic enforcement policies.
        """
        # Create a normal non-ff merge commit first (secure anchor comparison target)
        self._make_feature_with_change()
        pre_merge_sha = _head_sha(self.repo, "develop")
        merge_commit = self._non_ff_merge()
        # merge_commit^1 == pre_merge_sha (normal case)
        self.assertEqual(_head_sha(self.repo, f"{merge_commit}^1"), pre_merge_sha)

        # WR-440 Simulation: Case where pre_merge_develop_sha was captured as a separate commit
        # i.e. reset_target = bogus_unrelated_sha != merge_commit^1
        # At this time, _handle_anchor_failure must output advisory.
        # (The reset itself is in progress — advisory only)
        bogus_sha = "deadbeef" * 5  # 40 character fake SHA (failure when attempting actual reset)

        error_messages: list[str] = []

        def fake_error(msg: str) -> None:
            error_messages.append(msg)

        with mock.patch.object(
            _mp, "_git", side_effect=self._patched_git()
        ), mock.patch.object(_mp, "_error", side_effect=fake_error):
            _mp._handle_anchor_failure(
                merge_commit=merge_commit,
                feature_branch=self.feature_branch,
                reason="S6 simulated parent1 mismatch",
                pre_merge_develop_sha=bogus_sha,
            )

        all_errors = "\n".join(error_messages)
        # Check advisory marker
        self.assertIn(
            "[ANCHOR][WR-441]",
            all_errors,
            "parent1_mismatch advisory marker should be output",
        )
        self.assertIn(
            "Suspicious case",
            all_errors,
            "Advisory must specify Suspicious cases.",
        )

    def test_handle_anchor_failure_normal_case_no_advisory(self) -> None:
        """In the normal case (reset_target == merge_commit^1), advisory is not output (regression 0)."""
        self._make_feature_with_change()
        pre_merge_sha = _head_sha(self.repo, "develop")
        merge_commit = self._non_ff_merge()

        error_messages: list[str] = []

        def fake_error(msg: str) -> None:
            error_messages.append(msg)

        # ^2 Modify the rev-parse result to force anchor failure and call reset_target as normal
        orig = _mp._git
        fake_sha = "cafebabe" * 5

        def patched_git(*args, repo_path=None):
            if len(args) >= 2 and args[0] == "rev-parse" and args[1].endswith("^2"):
                return subprocess.CompletedProcess(
                    args=list(args),
                    returncode=0,
                    stdout=fake_sha + "\n",
                    stderr="",
                )
            return orig(*args, repo_path=self.repo)

        with mock.patch.object(
            _mp, "_git", side_effect=patched_git
        ), mock.patch.object(_mp, "_error", side_effect=fake_error):
            _mp._handle_anchor_failure(
                merge_commit=merge_commit,
                feature_branch=self.feature_branch,
                reason="S6 normal case",
                pre_merge_develop_sha=pre_merge_sha,
            )

        all_errors = "\n".join(error_messages)
        # parent1 match In a normal case, there should be no [WR-441] suspect case marker
        self.assertNotIn(
            "Suspicious case",
            all_errors,
            "In the normal reset_target == merge_commit^1 case, advisory should not be output.",
        )


if __name__ == "__main__":
    unittest.main()
