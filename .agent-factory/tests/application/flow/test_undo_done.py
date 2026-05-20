"""test undo done.py - Done Rollback System (T-905) + Integrated Test.

Phase 4 (T4.1~T4.4) Verification Range:
  T4.1 unit: _detect_push_state / _verify_merge_anchor / _force_done_to_review /
            _load_merge_commit
  T4.2 edge: reflog expiration / follow-up commit cumulative / brand name crash / run output
  T4.3 Integration: temporary git repo push pre reset branch / revert branch after push
  T4.4 Regression Verification: cmd done guard (merge commit storage) does not break dirty/Done flow

The test conforms to unittest pattern, environment (e.g. kanban directory, project root) cracking effect
git repo + module function as a monkeypatch
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

from flow import undo_done  # noqa: E402


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


def _setup_repo_with_merge(repo: str) -> tuple[str, str]:
    """construct a temporary repo with development + feature brand + merge commit.

    Returns:
        (merge commit sha, feature branch name) tuple.
    """
    _git_check(repo, "init", "-b", "develop")
    _git_check(repo, "config", "user.email", "test@example.com")
    _git_check(repo, "config", "user.name", "Test")

    init_file = os.path.join(repo, "README.md")
    with open(init_file, "w") as f:
        f.write("init\n")
    _git_check(repo, "add", "README.md")
    _git_check(repo, "commit", "-m", "init")

    # feature branch
    feature_branch = "feat/T-999-test"
    _git_check(repo, "checkout", "-b", feature_branch)
    work_file = os.path.join(repo, "work.py")
    with open(work_file, "w") as f:
        f.write("x = 1\n")
    _git_check(repo, "add", "work.py")
    _git_check(repo, "commit", "-m", "feat: add work")

    # --no-ff merge
    _git_check(repo, "checkout", "develop")
    _git_check(
        repo, "merge", "--no-ff", "-m", "merge feat/T-999-test", feature_branch
    )

    head = _git_check(repo, "rev-parse", "HEAD").stdout.strip()
    return head, feature_branch


# ─── T4.1 unit: _detect_push_state ──────────────────────────────────────────


class TestDetectPushState(unittest.TestCase):
    """detect push state: local / pushed / main three-quarter verification."""

    def setUp(self) -> None:
        self.repo = tempfile.mkdtemp(prefix="wf_test_undo_pushstate_")
        self.merge_commit, _ = _setup_repo_with_merge(self.repo)

    def tearDown(self) -> None:
        shutil.rmtree(self.repo, ignore_errors=True)

    def _run(self, sha: str) -> str:
        """Replace resolve project root to temporary repo and call  detect push state."""
        with mock.patch.object(undo_done, "resolve_project_root", return_value=self.repo):
            return undo_done._detect_push_state(sha)

    def test_local_when_no_remote_refs(self) -> None:
        """'local' return without origin/* refs."""
        state = self._run(self.merge_commit)
        self.assertEqual(state, "local")

    def test_pushed_when_origin_develop_present(self) -> None:
        """'pushed' return if origin/develop ref."""
        # bare remote generate push
        remote = tempfile.mkdtemp(prefix="wf_test_undo_remote_")
        try:
            _git_check(remote, "init", "--bare", "-b", "develop")
            _git_check(self.repo, "remote", "add", "origin", remote)
            _git_check(self.repo, "push", "origin", "develop")
            state = self._run(self.merge_commit)
            self.assertEqual(state, "pushed")
        finally:
            shutil.rmtree(remote, ignore_errors=True)

    def test_main_when_origin_main_present(self) -> None:
        """if origin/main ref is 'main' return (revert forced)."""
        remote = tempfile.mkdtemp(prefix="wf_test_undo_remote_main_")
        try:
            _git_check(remote, "init", "--bare", "-b", "develop")
            _git_check(self.repo, "remote", "add", "origin", remote)
            _git_check(self.repo, "push", "origin", "develop")
            # main branch in develop + push
            _git_check(self.repo, "branch", "main", "develop")
            _git_check(self.repo, "push", "origin", "main")
            state = self._run(self.merge_commit)
            self.assertEqual(state, "main")
        finally:
            shutil.rmtree(remote, ignore_errors=True)


# ─── T4.1 unit: _verify_merge_anchor ────────────────────────────────────────


class TestVerifyMergeAnchor(unittest.TestCase):
    """verify merge anchor: parent2 verification."""

    def setUp(self) -> None:
        self.repo = tempfile.mkdtemp(prefix="wf_test_undo_anchor_")
        self.merge_commit, self.feature_branch = _setup_repo_with_merge(self.repo)

    def tearDown(self) -> None:
        shutil.rmtree(self.repo, ignore_errors=True)

    def test_anchor_pass_when_parent2_matches_feature_tip(self) -> None:
        """top merge: merge commit^2 == feature branding tip."""
        with mock.patch.object(undo_done, "resolve_project_root", return_value=self.repo):
            # Pass if SystemExit does not occur
            try:
                undo_done._verify_merge_anchor(self.merge_commit, self.feature_branch)
            except SystemExit:
                self.fail("Top anchor verification cast SystemExit")

    def test_anchor_skip_when_feature_branch_deleted(self) -> None:
        """feature When the brand is already deleted, it passes through the skew."""
        _git_check(self.repo, "branch", "-D", self.feature_branch)
        with mock.patch.object(undo_done, "resolve_project_root", return_value=self.repo):
            # feature Brand Name Empty String (status after clearing)
            try:
                undo_done._verify_merge_anchor(self.merge_commit, "")
            except SystemExit:
                self.fail("After deleting the brand, anchor verification cast SystemExit")

    def test_anchor_fail_when_parent2_mismatches(self) -> None:
        """parent2 is expected branch tip and different if abort."""
        # feature Brands move to another SHA
        _git_check(self.repo, "checkout", self.feature_branch)
        bogus = os.path.join(self.repo, "bogus.py")
        with open(bogus, "w") as f:
            f.write("y = 2\n")
        _git_check(self.repo, "add", "bogus.py")
        _git_check(self.repo, "commit", "-m", "bogus extra")
        _git_check(self.repo, "checkout", "develop")

        with mock.patch.object(undo_done, "resolve_project_root", return_value=self.repo):
            with self.assertRaises(SystemExit):
                undo_done._verify_merge_anchor(self.merge_commit, self.feature_branch)


# ─── T4.1 unit: _force_done_to_review ───────────────────────────────────────


class TestForceDoneToReview(unittest.TestCase):
    """force done to review: Move the file + status renewal verification."""

    def setUp(self) -> None:
        self.tmp_root = tempfile.mkdtemp(prefix="wf_test_undo_force_")
        # kanban Director
        self.kanban_dir = os.path.join(self.tmp_root, ".agent-factory", "tickets")
        self.done_dir = os.path.join(self.kanban_dir, "done")
        self.review_dir = os.path.join(self.kanban_dir, "review")
        os.makedirs(self.done_dir, exist_ok=True)
        os.makedirs(self.review_dir, exist_ok=True)

        # Pile Ticket XML Writing (status=Done)
        self.ticket_id = "T-999"
        self.done_file = os.path.join(self.done_dir, f"{self.ticket_id}.xml")
        with open(self.done_file, "w", encoding="utf-8") as f:
            f.write(
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                "<ticket>\n"
                "  <metadata>\n"
                f"    <number>{self.ticket_id}</number>\n"
                "    <title>test</title>\n"
                "    <created>2026-05-07 12:00:00</created>\n"
                "    <updated>2026-05-07 12:00:00</updated>\n"
                "    <status>Done</status>\n"
                "    <command>implement</command>\n"
                "  </metadata>\n"
                "  <prompt />\n"
                "  <result />\n"
                "</ticket>\n"
            )

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_root, ignore_errors=True)

    def test_file_moved_and_status_updated(self) -> None:
        """The file will go to done/ review →/ and status will be updated to Review."""
        from flow import ticket_repository

        # STATUS DIR MAP and KANBAN * DIR
        patched_map = dict(ticket_repository.STATUS_DIR_MAP)
        patched_map["Done"] = self.done_dir
        patched_map["Review"] = self.review_dir

        with mock.patch.object(
            ticket_repository, "STATUS_DIR_MAP", patched_map
        ), mock.patch.object(
            ticket_repository, "KANBAN_DONE_DIR", self.done_dir
        ), mock.patch.object(
            ticket_repository, "KANBAN_REVIEW_DIR", self.review_dir
        ):
            new_path = undo_done._force_done_to_review(
                self.ticket_id, self.done_file
            )

        # Check if the file is moved to review/
        expected_path = os.path.join(self.review_dir, f"{self.ticket_id}.xml")
        self.assertEqual(os.path.normpath(new_path), os.path.normpath(expected_path))
        self.assertTrue(os.path.isfile(expected_path))
        self.assertFalse(os.path.isfile(self.done_file))

        # status check updated to Review (XML parsing)
        import xml.etree.ElementTree as ET
        tree = ET.parse(expected_path)
        status_elem = tree.getroot().find("metadata/status")
        self.assertIsNotNone(status_elem)
        self.assertEqual(status_elem.text, "Review")


# ─── T4.1 unit: _load_merge_commit ──────────────────────────────────────────


class TestLoadMergeCommit(unittest.TestCase):
    """load merge commit: result existence / missing + force / missing + non-force branch."""

    def setUp(self) -> None:
        self.tmp_root = tempfile.mkdtemp(prefix="wf_test_undo_loadmc_")
        self.ticket_file = os.path.join(self.tmp_root, "T-999.xml")
        self.ticket_id = "T-999"

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_root, ignore_errors=True)

    def _write_ticket(self, merge_commit: str = "") -> None:
        result_xml = (
            f"  <result>\n    <merge_commit>{merge_commit}</merge_commit>\n  </result>\n"
            if merge_commit
            else "  <result />\n"
        )
        with open(self.ticket_file, "w", encoding="utf-8") as f:
            f.write(
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                "<ticket>\n"
                "  <metadata>\n"
                f"    <number>{self.ticket_id}</number>\n"
                "    <title>test</title>\n"
                "    <created>2026-05-07 12:00:00</created>\n"
                "    <updated>2026-05-07 12:00:00</updated>\n"
                "    <status>Done</status>\n"
                "  </metadata>\n"
                "  <prompt />\n"
                f"{result_xml}"
                "</ticket>\n"
            )

    def test_returns_merge_commit_when_present(self) -> None:
        """result.merge commit"""
        self._write_ticket(merge_commit="abc123def456")
        sha = undo_done._load_merge_commit(self.ticket_id, self.ticket_file, force=False)
        self.assertEqual(sha, "abc123def456")

    def test_aborts_when_missing_and_no_force(self) -> None:
        """result.merge commit has no force=False if abort."""
        self._write_ticket(merge_commit="")
        with self.assertRaises(SystemExit):
            undo_done._load_merge_commit(
                self.ticket_id, self.ticket_file, force=False
            )

    def test_reflog_fallback_when_missing_and_force_no_match(self) -> None:
        """force=True but reflog no matching → abort (T4.2 reflog expire case)."""
        self._write_ticket(merge_commit="")

        # git call to blank stdout
        fake_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        with mock.patch.object(undo_done, "_git", return_value=fake_result):
            with self.assertRaises(SystemExit):
                undo_done._load_merge_commit(
                    self.ticket_id, self.ticket_file, force=True
                )

    def test_reflog_fallback_when_missing_and_force_with_match(self) -> None:
        """force=True and reflog matched → first candidate SHA return."""
        self._write_ticket(merge_commit="")

        fake_result = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout="abcdef1234567890 merge feat/T-999-test into develop\n",
            stderr="",
        )
        with mock.patch.object(undo_done, "_git", return_value=fake_result):
            sha = undo_done._load_merge_commit(
                self.ticket_id, self.ticket_file, force=True
            )
            self.assertEqual(sha, "abcdef1234567890")


# ─ T4.2 edge: Reset → revert auto force ─────────────────


class TestFollowupCommitsForceRevert(unittest.TestCase):
    """follow-up commits  strategy reset denied +  has followup commits=True."""

    def setUp(self) -> None:
        self.repo = tempfile.mkdtemp(prefix="wf_test_undo_followup_")
        self.merge_commit, _ = _setup_repo_with_merge(self.repo)

        # Add 1 Shift Commit
        extra = os.path.join(self.repo, "extra.py")
        with open(extra, "w") as f:
            f.write("z = 3\n")
        _git_check(self.repo, "add", "extra.py")
        _git_check(self.repo, "commit", "-m", "extra after merge")

    def tearDown(self) -> None:
        shutil.rmtree(self.repo, ignore_errors=True)

    def test_has_followup_commits_returns_true(self) -> None:
        """Development HEAD is a true if it is a commit ahead of merge commit."""
        with mock.patch.object(undo_done, "resolve_project_root", return_value=self.repo):
            self.assertTrue(undo_done._has_followup_commits(self.merge_commit))

    def test_strategy_reset_aborts_with_followup(self) -> None:
        """strategy reset call abort with follow-up commit check."""
        with mock.patch.object(undo_done, "resolve_project_root", return_value=self.repo):
            with self.assertRaises(SystemExit):
                undo_done._strategy_reset(self.merge_commit, "T-999")

    def test_strategy_reset_no_followup_succeeds(self) -> None:
        """If there is no follow-up commit, reset success + head moves to merge commit^."""
        repo2 = tempfile.mkdtemp(prefix="wf_test_undo_reset_clean_")
        try:
            merge_commit, _ = _setup_repo_with_merge(repo2)
            with mock.patch.object(undo_done, "resolve_project_root", return_value=repo2):
                undo_done._strategy_reset(merge_commit, "T-999")

            # head == merge commit^
            new_head = _git_check(repo2, "rev-parse", "HEAD").stdout.strip()
            parent = _git_check(repo2, "rev-parse", f"{merge_commit}^").stdout.strip()
            self.assertEqual(new_head, parent)
        finally:
            shutil.rmtree(repo2, ignore_errors=True)


# ─ T4.2 Edge: Brand Name Collision ( check branch worktree clear) ─────────────


class TestBranchWorktreeClear(unittest.TestCase):
    """check branch worktree clear: pass abort when occupied."""

    def setUp(self) -> None:
        self.repo = tempfile.mkdtemp(prefix="wf_test_undo_clear_")
        _git_check(self.repo, "init", "-b", "develop")
        _git_check(self.repo, "config", "user.email", "test@example.com")
        _git_check(self.repo, "config", "user.name", "Test")

        with open(os.path.join(self.repo, "README.md"), "w") as f:
            f.write("init\n")
        _git_check(self.repo, "add", "README.md")
        _git_check(self.repo, "commit", "-m", "init")

    def tearDown(self) -> None:
        shutil.rmtree(self.repo, ignore_errors=True)

    def test_aborts_when_branch_exists(self) -> None:
        """The feature of the same ticket is the force=False city abort."""
        with mock.patch.object(
            undo_done, "get_feature_branch_for_ticket", return_value="feat/T-999-test"
        ), mock.patch.object(
            undo_done, "get_worktree_path", return_value=None
        ):
            with self.assertRaises(SystemExit):
                undo_done._check_branch_worktree_clear("T-999", force=False)

    def test_passes_when_branch_exists_with_force(self) -> None:
        """force=True is passed even if the oil is found (hard)."""
        with mock.patch.object(
            undo_done, "get_feature_branch_for_ticket", return_value="feat/T-999-test"
        ), mock.patch.object(
            undo_done, "get_worktree_path", return_value="/tmp/some-worktree"
        ):
            existing_branch, existing_wt = undo_done._check_branch_worktree_clear(
                "T-999", force=True
            )
            self.assertEqual(existing_branch, "feat/T-999-test")
            self.assertEqual(existing_wt, "/tmp/some-worktree")

    def test_passes_when_neither_exists(self) -> None:
        """If you don’t have any brand/worktree (None, None) return."""
        with mock.patch.object(
            undo_done, "get_feature_branch_for_ticket", return_value=None
        ), mock.patch.object(
            undo_done, "get_worktree_path", return_value=None
        ):
            existing_branch, existing_wt = undo_done._check_branch_worktree_clear(
                "T-999", force=False
            )
            self.assertIsNone(existing_branch)
            self.assertIsNone(existing_wt)


# ─ T4.2 edge: run output conservation (reset/revert is working tree no external influence) ─


class TestRunsArtifactsPreserved(unittest.TestCase):
    """reset / revert .agent-factory/runs/ directory in any quarter no impact.

    run/ .gitignore is the target or git tracking external file,
    git operation Verifies the fact that it changes only the tracking file of working tree.
    """

    def setUp(self) -> None:
        self.repo = tempfile.mkdtemp(prefix="wf_test_undo_runs_preserve_")
        self.merge_commit, _ = _setup_repo_with_merge(self.repo)

        # . gitignore to run/include
        gitignore = os.path.join(self.repo, ".gitignore")
        with open(gitignore, "w") as f:
            f.write(".agent-factory/runs/\n")
        _git_check(self.repo, "add", ".gitignore")
        _git_check(self.repo, "commit", "-m", "add gitignore")

        # run/ directory output creation (untracked)
        self.runs_dir = os.path.join(self.repo, ".agent-factory", "runs", "20260507-141035")
        os.makedirs(self.runs_dir, exist_ok=True)
        self.artifact = os.path.join(self.runs_dir, "report.md")
        with open(self.artifact, "w") as f:
            f.write("Output content\\n")

    def tearDown(self) -> None:
        shutil.rmtree(self.repo, ignore_errors=True)

    def test_artifact_survives_reset(self) -> None:
        """the untracked output even after reset --hard is preserved."""
        # reset --hard <merge commit>
        # Develop tip conservation safely; check output conservation only
        _git_check(self.repo, "reset", "--hard", "HEAD")
        self.assertTrue(os.path.isfile(self.artifact))
        with open(self.artifact, "r") as f:
            self.assertEqual(f.read(), "Output content\\n")

    def test_artifact_survives_revert(self) -> None:
        """untracked output even after revert -m 1 is preserved."""
        _git_check(
            self.repo, "revert", "-m", "1", "--no-edit", self.merge_commit
        )
        self.assertTrue(os.path.isfile(self.artifact))


# ──────────────────────────────────────────────────


class TestIntegrationResetFlow(unittest.TestCase):
    """Integration: Verify the reset branch is normal operation.

    `main()` The entire flow is worktree manager.create worktree / Director of the Kanban
    Required but  strategy reset sole +  detect push state +  has followup commits
    to validate push-pre-quarter operation as a combination.
    """

    def setUp(self) -> None:
        self.repo = tempfile.mkdtemp(prefix="wf_test_undo_integration_reset_")
        self.merge_commit, _ = _setup_repo_with_merge(self.repo)

    def tearDown(self) -> None:
        shutil.rmtree(self.repo, ignore_errors=True)

    def test_local_no_followup_uses_reset(self) -> None:
        """Before pushing + no follow-up commit → select quarterly + run normal."""
        with mock.patch.object(undo_done, "resolve_project_root", return_value=self.repo):
            push_state = undo_done._detect_push_state(self.merge_commit)
            has_followup = undo_done._has_followup_commits(self.merge_commit)

            self.assertEqual(push_state, "local")
            self.assertFalse(has_followup)

            # reset
            undo_done._strategy_reset(self.merge_commit, "T-999")

            # head to merge commit^
            new_head = _git_check(self.repo, "rev-parse", "HEAD").stdout.strip()
            parent = _git_check(
                self.repo, "rev-parse", f"{self.merge_commit}^"
            ).stdout.strip()
            self.assertEqual(new_head, parent)


# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────


class TestIntegrationRevertFlow(unittest.TestCase):
    """Integration: revert branch normal operation + new commit added."""

    def setUp(self) -> None:
        self.repo = tempfile.mkdtemp(prefix="wf_test_undo_integration_revert_")
        self.merge_commit, _ = _setup_repo_with_merge(self.repo)

        # bare remote + push (origin/develop reach)
        self.remote = tempfile.mkdtemp(prefix="wf_test_undo_remote_")
        _git_check(self.remote, "init", "--bare", "-b", "develop")
        _git_check(self.repo, "remote", "add", "origin", self.remote)
        _git_check(self.repo, "push", "origin", "develop")

    def tearDown(self) -> None:
        shutil.rmtree(self.repo, ignore_errors=True)
        shutil.rmtree(self.remote, ignore_errors=True)

    def test_pushed_uses_revert(self) -> None:
        """After push → revert branch selection + add new commit."""
        with mock.patch.object(undo_done, "resolve_project_root", return_value=self.repo):
            push_state = undo_done._detect_push_state(self.merge_commit)
            self.assertEqual(push_state, "pushed")

            # revert
            undo_done._strategy_revert(self.merge_commit)

            # new HEAD != merge commit (revert commit added)
            new_head = _git_check(self.repo, "rev-parse", "HEAD").stdout.strip()
            self.assertNotEqual(new_head, self.merge_commit)

            # Commit messages include 'Revert'
            log = _git_check(self.repo, "log", "-1", "--format=%s").stdout.strip()
            self.assertIn("Revert", log)


# ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────


class TestCmdDoneRegressionGuard(unittest.TestCase):
    """T-906 (Review→Done DnD) cmd done to change W01 (merge commit storage)
    Unexpected static + validation of operation.

    Verification Point:
      1. FAQ merge commit storage occurs only inside the merge success branch (no influence when merge failed)
      2. FAQ dirty check / Done guard flow remains true (with guard code in cmd done source)
      3. FAQs update result call does not break cmd done itself when wrapping with try/except
    """

    def setUp(self) -> None:
        self.kanban_cli_path = os.path.join(
            _ENGINE_DIR, "flow", "kanban_cli.py"
        )
        with open(self.kanban_cli_path, "r", encoding="utf-8") as f:
            self.source = f.read()

    def test_merge_commit_save_inside_success_branch(self) -> None:
        """update result call 'merge result.success' branch + 'merge commit'
        static verification that is located within the truthy inspection.
        """
        # 'else:' Then you need 'update result(...)' (merge result.success Branch)
        # at the same time the 'if merge result.merge commit:' guard must exist
        self.assertIn("if merge_result.merge_commit:", self.source)
        # update result check if the call is wrapped in try/except
        self.assertRegex(
            self.source,
            r"if merge_result\.merge_commit:\s*\n\s*try:",
        )
        # [WARN] output (cmd done not abort itself)
        self.assertIn("result.merge commit save failed", self.source)

    def test_dirty_check_guard_preserved(self) -> None:
        """dirty worktree check code exists in cmd done (T-906 protection)."""
        self.assertIn("has_uncommitted_changes(_wt_path)", self.source)
        self.assertIn("Copyright (c) Micommit All Rights Reserved.", self.source)
        self.assertIn("Block Done transformation", self.source)

    def test_done_guard_flow_preserved(self) -> None:
        """Done Core Flow (find ticket file → update ticket status → Move File)
        This will be maintained.
        """
        # merge commit to enter core flow after saving
        self.assertIn('update_ticket_status(ticket_file, "Done")', self.source)
        self.assertIn('move_ticket_to_status_dir(ticket_file, "Done")', self.source)

    def test_update_result_argparse_extension(self) -> None:
        """--merge-commit option added to argparse update-result subdirection."""
        self.assertIn('"--merge-commit"', self.source)
        self.assertIn('dest="merge_commit"', self.source)


# ─ T4.4 Regression verification: ticket repository result fields whitelist ──────────


class TestResultFieldsWhitelist(unittest.TestCase):
    """ticket repository.update result's result fields whitelist
    static verification that contains 'merge commit'.
    """

    def test_merge_commit_in_whitelist(self) -> None:
        from flow import ticket_repository

        # update result's source from result fields tuning
        import inspect
        source = inspect.getsource(ticket_repository.update_result)
        self.assertIn('"merge_commit"', source)

    def test_parse_includes_merge_commit(self) -> None:
        """parse ticket xml also must include the merge commit field to result."""
        from flow import ticket_repository

        import inspect
        source = inspect.getsource(ticket_repository.parse_ticket_xml)
        self.assertIn('"merge_commit"', source)


if __name__ == "__main__":
    unittest.main()
