"""test merge anchor safety.py - merge anchor safety revolving guard testing (T-410).

Payment Terms:
  T1: already-up-to-date / ff skip —
      feature is developed by ancestor, temporary repo from
      stage2 5 verify merge anchor call → True return + "skip" log + reset confirmation.

  T2: non-ff normal passing —
      feature is developed in a quarterly temporary repo in non-ff merge commit generation after
      stage2 5 verify merge anchor call → True return + reset confirmation.
      merge commit^2 == function HEAD SHA validation.

  T3: rollback (T-403 revolving guard) after non-ff verification failure —
      Developing Pre-head Commit 2 + Feature Quarter + Non-ff After merge
      as a mock  git to modulate the ^2 result and forced the anchor verification failure.
      stage2 5 verify merge anchor returns False +  handle anchor failure
      git reset --hard <pre merge develop sha> call + pre-earhead commit
      create log

  T4: HEAD^ fallback —
      pre merge develop sha
      fallback + alert log output to the existing HEAD^ path.
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

import flow.merge_pipeline as _mp  # noqa: E402


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


def _setup_base_repo(repo: str) -> None:
    """Init + user config + base commit."""
    _git_check(repo, "init", "-b", "develop")
    _git_check(repo, "config", "user.email", "test@example.com")
    _git_check(repo, "config", "user.name", "Test")

    work_file = os.path.join(repo, "work.py")
    with open(work_file, "w") as f:
        f.write('x = "base"\n')
    _git_check(repo, "add", "work.py")
    _git_check(repo, "commit", "-m", "init")


def _get_head_sha(repo: str) -> str:
    """Currently, we return develop HEAD SHA."""
    result = _git(repo, "rev-parse", "HEAD")
    assert result.returncode == 0
    return result.stdout.strip()


def _get_log_shas(repo: str, n: int = 10) -> list[str]:
    """newest first"""
    result = _git(repo, "log", "--format=%H", f"-{n}")
    assert result.returncode == 0
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


# ─── T1: already-up-to-date / ff skip ────────────────────────────────────────


class TestVerifyMergeAnchorAlreadyUpToDateSkip(unittest.TestCase):
    """If the feature is developed ancestor, the anchor verification must be skipd.

    Scenario: feature brand is already included in develop
    "Already up to date." is returned
    new merge commit is not created. merge commit == pre merge develop sha
    stage2 5 verify merge anchor should return true.
    """

    def setUp(self) -> None:
        self.repo = tempfile.mkdtemp(prefix="wf_test_t410_t1_")
        _setup_base_repo(self.repo)

        # Commit after creating a feature brand
        self.feature_branch = "feat/T-410-t1-test"
        _git_check(self.repo, "checkout", "-b", self.feature_branch)
        work_file = os.path.join(self.repo, "work.py")
        with open(work_file, "w") as f:
            f.write('x = "feature"\n')
        _git_check(self.repo, "add", "work.py")
        _git_check(self.repo, "commit", "-m", "feat: add feature commit")

        # Develop and include feature commits to fast-forward
        _git_check(self.repo, "checkout", "develop")
        _git_check(self.repo, "merge", "--ff-only", self.feature_branch)

        # --no-ff --to-date
        self.pre_merge_sha = _get_head_sha(self.repo)
        merge_result = _git(
            self.repo, "merge", "--no-ff", self.feature_branch
        )
        # "Already up to date." — merge_commit == develop HEAD == pre_merge_sha
        self.merge_commit = _get_head_sha(self.repo)
        self.assertEqual(
            self.merge_commit,
            self.pre_merge_sha,
            "already-up-to-date The head cannot be changed from the case",
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.repo, ignore_errors=True)

    def test_already_up_to_date_returns_true_and_no_reset(self) -> None:
        """True return + reset from already-up-to-date case."""
        # git patches to repo path, and force is worktree enabled to True.
        # stage2 5 verify merge anchor inside  git call to port real repo
        # inject repo path.
        orig_git = _mp._git

        def patched_git(*args, repo_path=None):
            return orig_git(*args, repo_path=self.repo)

        printed_lines: list[str] = []

        def fake_print(*args, **kwargs):
            printed_lines.append(" ".join(str(a) for a in args))

        with mock.patch(
            "flow.worktree_manager.is_worktree_enabled", return_value=True
        ), mock.patch.object(_mp, "_git", side_effect=patched_git), mock.patch(
            "builtins.print", side_effect=fake_print
        ):
            result = _mp._stage2_5_verify_merge_anchor(
                merge_commit=self.merge_commit,
                feature_branch=self.feature_branch,
                dry_run=False,
                pre_merge_develop_sha=self.pre_merge_sha,
            )

        self.assertTrue(result, "stage2 5 verify merge anchor should return true")

        # "skip" related logs should be output
        all_output = "\n".join(printed_lines)
        self.assertIn(
            "already-up-to-date",
            all_output,
            "already-up-to-date skip logs must be output",
        )

        # development head should not be changed (reset check)
        head_after = _get_head_sha(self.repo)
        self.assertEqual(
            head_after,
            self.pre_merge_sha,
            "reset This call cannot be changed by HEAD",
        )


# ───────────────────────────────────────────────────────────────────────


class TestVerifyMergeAnchorNonFfPass(unittest.TestCase):
    """feature has been quartered in development and non-ff merge commit is generated
    Anchor validation must pass (True).

    Verification Point:
      - merge_commit^2 == feature HEAD SHA
      - _stage2_5_verify_merge_anchor → True
      - reset (develop head retention)
    """

    def setUp(self) -> None:
        self.repo = tempfile.mkdtemp(prefix="wf_test_t410_t2_")
        _setup_base_repo(self.repo)

        # create a brand name and commit
        self.feature_branch = "feat/T-410-t2-test"
        _git_check(self.repo, "checkout", "-b", self.feature_branch)
        work_file = os.path.join(self.repo, "work.py")
        with open(work_file, "a") as f:
            f.write('y = "feature"\n')
        _git_check(self.repo, "add", "work.py")
        _git_check(self.repo, "commit", "-m", "feat: add y")
        self.feature_head_sha = _get_head_sha(self.repo)

        # Developing non-ff merge.
        # We do not add a separate commit to develop.
        # reason: git diff merge commit^2 merge commit validation (delete 2)
        # "object to object",
        # If you have additional changes to develop, that change is included in diff
        # non-empty → Verified failure. Despite the normal non-ff merge.
        # non-ff merge structure(merge commit to ^2 parent existence) is developed separately
        # --no-ff flags can be forced.
        _git_check(self.repo, "checkout", "develop")

        # pre merge SHA record after non-ff merge
        self.pre_merge_sha = _get_head_sha(self.repo)
        _git_check(
            self.repo,
            "merge",
            "--no-ff",
            "-m",
            f"Merge {self.feature_branch} into develop",
            self.feature_branch,
        )
        self.merge_commit = _get_head_sha(self.repo)

    def tearDown(self) -> None:
        shutil.rmtree(self.repo, ignore_errors=True)

    def test_non_ff_passes_and_no_reset(self) -> None:
        """non-ff merger after anchor verification pass + reset."""
        # ^2 SHA == HEAD SHA preview
        parent2_result = _git(self.repo, "rev-parse", f"{self.merge_commit}^2")
        self.assertEqual(parent2_result.returncode, 0)
        self.assertEqual(
            parent2_result.stdout.strip(),
            self.feature_head_sha,
            "merge commit^2 must match feature HEAD SHA",
        )

        orig_git = _mp._git

        def patched_git(*args, repo_path=None):
            return orig_git(*args, repo_path=self.repo)

        with mock.patch(
            "flow.worktree_manager.is_worktree_enabled", return_value=True
        ), mock.patch.object(_mp, "_git", side_effect=patched_git):
            result = _mp._stage2_5_verify_merge_anchor(
                merge_commit=self.merge_commit,
                feature_branch=self.feature_branch,
                dry_run=False,
                pre_merge_develop_sha=self.pre_merge_sha,
            )

        self.assertTrue(result, "Anchor verification must be passed (True)")

        # development head should not be changed
        head_after = _get_head_sha(self.repo)
        self.assertEqual(
            head_after,
            self.merge_commit,
            "head must be merge commit when normal passing",
        )


# ────────────────────────────────────────────────────────────────────────────────────────────────


class TestVerifyMergeAnchorRollbackPreservesAheadCommits(unittest.TestCase):
    """executed with pre merge develop sha when anchor verification failed
    The advance ahead commitment of develop should be preserved (T-403 revolving guard).

    Scenario:
      1. Add two advance commits to develop (a1, a2)
      2. Feature Branches + Commitment
      3. FAQs create non-ff merge → merge commit
      4. Modulation of ^2 rev-parse results with fake SHA
         → Anchor validation failed
      5. FAQs  stage2 5 verify merge anchor → False return check
      git reset --hard pre merge develop sha (== a2)
      7. Development log in a1, a2 is preservation check
    """

    def setUp(self) -> None:
        self.repo = tempfile.mkdtemp(prefix="wf_test_t410_t3_")
        _setup_base_repo(self.repo)

        # 2 additional pre-mittance to develop
        work_file = os.path.join(self.repo, "work.py")

        with open(work_file, "a") as f:
            f.write('a1 = "ahead1"\n')
        _git_check(self.repo, "add", "work.py")
        _git_check(self.repo, "commit", "-m", "ahead1: pre-existing commit")
        self.ahead1_sha = _get_head_sha(self.repo)

        with open(work_file, "a") as f:
            f.write('a2 = "ahead2"\n')
        _git_check(self.repo, "add", "work.py")
        _git_check(self.repo, "commit", "-m", "ahead2: pre-existing commit")
        self.ahead2_sha = _get_head_sha(self.repo)

        # create a brand name and commit
        self.feature_branch = "feat/T-410-t3-test"
        _git_check(self.repo, "checkout", "-b", self.feature_branch)
        feat_file = os.path.join(self.repo, "feat.py")
        with open(feat_file, "w") as f:
            f.write('feat = "T-410"\n')
        _git_check(self.repo, "add", "feat.py")
        _git_check(self.repo, "commit", "-m", "feat: add feat.py")
        self.feature_head_sha = _get_head_sha(self.repo)

        # non-ff merge
        _git_check(self.repo, "checkout", "develop")
        self.pre_merge_sha = _get_head_sha(self.repo)
        self.assertEqual(
            self.pre_merge_sha,
            self.ahead2_sha,
            "pre merge sha should be ahead2",
        )
        _git_check(
            self.repo,
            "merge",
            "--no-ff",
            "-m",
            f"Merge {self.feature_branch} into develop",
            self.feature_branch,
        )
        self.merge_commit = _get_head_sha(self.repo)

    def tearDown(self) -> None:
        shutil.rmtree(self.repo, ignore_errors=True)

    def test_anchor_failure_rolls_back_to_pre_merge_sha(self) -> None:
        """anchor verification failed → False return + reset to pre merge sha + ahead commits preserved."""
        orig_git = _mp._git
        fake_sha = "deadbeef" * 5  # 40-Piece Fake SHA

        def patched_git(*args, repo_path=None):
            # ^2 rev-parse call only modulates anchor verification failed
            if len(args) >= 2 and args[0] == "rev-parse" and args[1].endswith("^2"):
                return subprocess.CompletedProcess(
                    args=list(args),
                    returncode=0,
                    stdout=fake_sha + "\n",
                    stderr="",
                )
            return orig_git(*args, repo_path=self.repo)

        with mock.patch(
            "flow.worktree_manager.is_worktree_enabled", return_value=True
        ), mock.patch.object(_mp, "_git", side_effect=patched_git):
            result = _mp._stage2_5_verify_merge_anchor(
                merge_commit=self.merge_commit,
                feature_branch=self.feature_branch,
                dry_run=False,
                pre_merge_develop_sha=self.pre_merge_sha,
            )

        self.assertFalse(result, "return False when anchor verification fails")

        # head check after rollback: pre merge sha (== ahead2) should be returned
        head_after = _get_head_sha(self.repo)
        self.assertEqual(
            head_after,
            self.pre_merge_sha,
            f"head must be pre merge sha(   FIELD 0   ) after rollback",
        )

        # Pre-head Commit 2 (ahead1, ahead2) should be preserved in log
        log_shas = _get_log_shas(self.repo, n=10)
        self.assertIn(
            self.ahead1_sha,
            log_shas,
            "ahead1 commit should be preserved in this develop log",
        )
        self.assertIn(
            self.ahead2_sha,
            log_shas,
            "forward2 commit should be preserved in this develop log",
        )


# ─── T4: HEAD^ fallback ───────────────────────────────────────────────────────


class TestHandleAnchorFailureHeadCaretFallback(unittest.TestCase):
    """pre merge develop sha
    reset + alert log output to HEAD^ fallback path.

    Verification Point:
      - reset call target "HEAD^" (bin pre merge develop sha case)
      -  error to fallback alert message output
    """

    def setUp(self) -> None:
        self.repo = tempfile.mkdtemp(prefix="wf_test_t410_t4_")
        _setup_base_repo(self.repo)

        # non-ff merge commit to create one and HEAD^ makes it available
        self.feature_branch = "feat/T-410-t4-test"
        _git_check(self.repo, "checkout", "-b", self.feature_branch)
        feat_file = os.path.join(self.repo, "feat4.py")
        with open(feat_file, "w") as f:
            f.write('feat4 = True\n')
        _git_check(self.repo, "add", "feat4.py")
        _git_check(self.repo, "commit", "-m", "feat4: add feat4.py")

        _git_check(self.repo, "checkout", "develop")
        self.pre_merge_sha = _get_head_sha(self.repo)
        _git_check(
            self.repo,
            "merge",
            "--no-ff",
            "-m",
            "Merge feat4 into develop",
            self.feature_branch,
        )
        self.merge_commit = _get_head_sha(self.repo)

    def tearDown(self) -> None:
        shutil.rmtree(self.repo, ignore_errors=True)

    def test_head_caret_fallback_with_warning(self) -> None:
        """pre merge develop sha empty string → HEAD^ fallback + warning log."""
        orig_git = _mp._git

        def patched_git(*args, repo_path=None):
            return orig_git(*args, repo_path=self.repo)

        error_messages: list[str] = []

        def fake_error(msg: str) -> None:
            error_messages.append(msg)

        with mock.patch.object(_mp, "_git", side_effect=patched_git), mock.patch.object(
            _mp, "_error", side_effect=fake_error
        ):
            # pre merge develop sha
            _mp._handle_anchor_failure(
                merge_commit=self.merge_commit,
                feature_branch=self.feature_branch,
                reason="T4 test: forced failure",
                pre_merge_develop_sha="",
            )

        # fallback warning log confirmation
        all_errors = "\n".join(error_messages)
        self.assertIn(
            "HEAD^",
            all_errors,
            "HEAD^ fallback warning message should be output",
        )

        # development head must be pre merge sha
        head_after = _get_head_sha(self.repo)
        self.assertEqual(
            head_after,
            self.pre_merge_sha,
            "HEAD^ rollback after development HEAD should be pre merge sha",
        )


if __name__ == "__main__":
    unittest.main()
