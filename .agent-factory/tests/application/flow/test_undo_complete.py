"""test undo_complete.py - Complete Rollback System (WR-905) + Integrated Test.

Phase 4 (T4.1~T4.4) Verification Range:
  T4.1 unit: _detect_push_state / _verify_merge_anchor / _force_complete_to_verifying /
            _load_merge_commit
  T4.2 edge: reflog expiration / follow-up commit cumulative / brand name crash / run output
  T4.3 Integration: temporary git repo push pre reset branch / revert branch after push
  T4.4 Regression Verification: cmd complete guard (merge commit storage) does not break dirty/Complete flow

The test conforms to unittest pattern, environment (e.g. conveyor directory, project root) cracking effect
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

from flow import undo_complete  # noqa: E402


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
    feature_branch = "feat/WR-999-test"
    _git_check(repo, "checkout", "-b", feature_branch)
    work_file = os.path.join(repo, "work.py")
    with open(work_file, "w") as f:
        f.write("x = 1\n")
    _git_check(repo, "add", "work.py")
    _git_check(repo, "commit", "-m", "feat: add work")

    # --no-ff merge
    _git_check(repo, "checkout", "develop")
    _git_check(
        repo, "merge", "--no-ff", "-m", "merge feat/WR-999-test", feature_branch
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
        with mock.patch.object(undo_complete, "resolve_project_root", return_value=self.repo):
            return undo_complete._detect_push_state(sha)

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
        with mock.patch.object(undo_complete, "resolve_project_root", return_value=self.repo):
            # Pass if SystemExit does not occur
            try:
                undo_complete._verify_merge_anchor(self.merge_commit, self.feature_branch)
            except SystemExit:
                self.fail("Top anchor verification cast SystemExit")

    def test_anchor_skip_when_feature_branch_deleted(self) -> None:
        """feature When the brand is already deleted, it passes through the skew."""
        _git_check(self.repo, "branch", "-D", self.feature_branch)
        with mock.patch.object(undo_complete, "resolve_project_root", return_value=self.repo):
            # feature Brand Name Empty String (status after clearing)
            try:
                undo_complete._verify_merge_anchor(self.merge_commit, "")
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

        with mock.patch.object(undo_complete, "resolve_project_root", return_value=self.repo):
            with self.assertRaises(SystemExit):
                undo_complete._verify_merge_anchor(self.merge_commit, self.feature_branch)


# ─── T4.1 unit: _force_complete_to_verifying ───────────────────────────────────────


class TestForceCompleteToVerifying(unittest.TestCase):
    """force complete to verifying: Move the file + status renewal verification."""

    def setUp(self) -> None:
        self.tmp_root = tempfile.mkdtemp(prefix="wf_test_undo_force_")
        # conveyor Director
        self.conveyor_dir = os.path.join(self.tmp_root, ".agent-factory", "work-requests")
        self.complete_dir = os.path.join(self.conveyor_dir, "complete")
        self.verifying_dir = os.path.join(self.conveyor_dir, "verifying")
        os.makedirs(self.complete_dir, exist_ok=True)
        os.makedirs(self.verifying_dir, exist_ok=True)

        # Pile WorkRequest XML Writing (status=Complete)
        self.work_request_number = "WR-999"
        self.complete_file = os.path.join(self.complete_dir, f"{self.work_request_number}.xml")
        with open(self.complete_file, "w", encoding="utf-8") as f:
            f.write(
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                "<work_request>\n"
                "  <metadata>\n"
                f"    <number>{self.work_request_number}</number>\n"
                "    <title>test</title>\n"
                "    <created>2026-05-07 12:00:00</created>\n"
                "    <updated>2026-05-07 12:00:00</updated>\n"
                "    <status>Complete</status>\n"
                "    <command>implement</command>\n"
                "  </metadata>\n"
                "  <prompt />\n"
                "  <result />\n"
                "</work_request>\n"
            )

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_root, ignore_errors=True)

    def test_file_moved_and_status_updated(self) -> None:
        """The file will go to complete/ verifying →/ and status will be updated to Verifying."""
        from flow import work_request_repository

        # STATUS DIR MAP and CONVEYOR * DIR
        patched_map = dict(work_request_repository.STATUS_DIR_MAP)
        patched_map["Complete"] = self.complete_dir
        patched_map["Verifying"] = self.verifying_dir

        with mock.patch.object(
            work_request_repository, "STATUS_DIR_MAP", patched_map
        ), mock.patch.object(
            work_request_repository, "CONVEYOR_COMPLETE_DIR", self.complete_dir
        ), mock.patch.object(
            work_request_repository, "CONVEYOR_VERIFYING_DIR", self.verifying_dir
        ):
            new_path = undo_complete._force_complete_to_verifying(
                self.work_request_number, self.complete_file
            )

        # Check if the file is moved to verifying/
        expected_path = os.path.join(self.verifying_dir, f"{self.work_request_number}.xml")
        self.assertEqual(os.path.normpath(new_path), os.path.normpath(expected_path))
        self.assertTrue(os.path.isfile(expected_path))
        self.assertFalse(os.path.isfile(self.complete_file))

        # status check updated to Verifying (XML parsing)
        import xml.etree.ElementTree as ET
        tree = ET.parse(expected_path)
        status_elem = tree.getroot().find("metadata/status")
        self.assertIsNotNone(status_elem)
        self.assertEqual(status_elem.text, "Verifying")


# ─── T4.1 unit: _load_merge_commit ──────────────────────────────────────────


class TestLoadMergeCommit(unittest.TestCase):
    """load merge commit: result existence / missing + force / missing + non-force branch."""

    def setUp(self) -> None:
        self.tmp_root = tempfile.mkdtemp(prefix="wf_test_undo_loadmc_")
        self.work_request_file = os.path.join(self.tmp_root, "WR-999.xml")
        self.work_request_number = "WR-999"

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_root, ignore_errors=True)

    def _write_work_request(self, merge_commit: str = "") -> None:
        result_xml = (
            f"  <result>\n    <merge_commit>{merge_commit}</merge_commit>\n  </result>\n"
            if merge_commit
            else "  <result />\n"
        )
        with open(self.work_request_file, "w", encoding="utf-8") as f:
            f.write(
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                "<work_request>\n"
                "  <metadata>\n"
                f"    <number>{self.work_request_number}</number>\n"
                "    <title>test</title>\n"
                "    <created>2026-05-07 12:00:00</created>\n"
                "    <updated>2026-05-07 12:00:00</updated>\n"
                "    <status>Complete</status>\n"
                "  </metadata>\n"
                "  <prompt />\n"
                f"{result_xml}"
                "</work_request>\n"
            )

    def test_returns_merge_commit_when_present(self) -> None:
        """result.merge commit"""
        self._write_work_request(merge_commit="abc123def456")
        sha = undo_complete._load_merge_commit(self.work_request_number, self.work_request_file, force=False)
        self.assertEqual(sha, "abc123def456")

    def test_aborts_when_missing_and_no_force(self) -> None:
        """result.merge commit has no force=False if abort."""
        self._write_work_request(merge_commit="")
        with self.assertRaises(SystemExit):
            undo_complete._load_merge_commit(
                self.work_request_number, self.work_request_file, force=False
            )

    def test_reflog_fallback_when_missing_and_force_no_match(self) -> None:
        """force=True but reflog no matching → abort (T4.2 reflog expire case)."""
        self._write_work_request(merge_commit="")

        # git call to blank stdout
        fake_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        with mock.patch.object(undo_complete, "_git", return_value=fake_result):
            with self.assertRaises(SystemExit):
                undo_complete._load_merge_commit(
                    self.work_request_number, self.work_request_file, force=True
                )

    def test_reflog_fallback_when_missing_and_force_with_match(self) -> None:
        """force=True and reflog matched → first candidate SHA return."""
        self._write_work_request(merge_commit="")

        fake_result = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout="abcdef1234567890 merge feat/WR-999-test into develop\n",
            stderr="",
        )
        with mock.patch.object(undo_complete, "_git", return_value=fake_result):
            sha = undo_complete._load_merge_commit(
                self.work_request_number, self.work_request_file, force=True
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
        with mock.patch.object(undo_complete, "resolve_project_root", return_value=self.repo):
            self.assertTrue(undo_complete._has_followup_commits(self.merge_commit))

    def test_strategy_reset_aborts_with_followup(self) -> None:
        """strategy reset call abort with follow-up commit check."""
        with mock.patch.object(undo_complete, "resolve_project_root", return_value=self.repo):
            with self.assertRaises(SystemExit):
                undo_complete._strategy_reset(self.merge_commit, "WR-999")

    def test_strategy_reset_no_followup_succeeds(self) -> None:
        """If there is no follow-up commit, reset success + head moves to merge commit^."""
        repo2 = tempfile.mkdtemp(prefix="wf_test_undo_reset_clean_")
        try:
            merge_commit, _ = _setup_repo_with_merge(repo2)
            with mock.patch.object(undo_complete, "resolve_project_root", return_value=repo2):
                undo_complete._strategy_reset(merge_commit, "WR-999")

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
        """The feature of the same work_request is the force=False city abort."""
        with mock.patch.object(
            undo_complete, "get_feature_branch_for_work_request", return_value="feat/WR-999-test"
        ), mock.patch.object(
            undo_complete, "get_worktree_path", return_value=None
        ):
            with self.assertRaises(SystemExit):
                undo_complete._check_branch_worktree_clear("WR-999", force=False)

    def test_passes_when_branch_exists_with_force(self) -> None:
        """force=True is passed even if the oil is found (hard)."""
        with mock.patch.object(
            undo_complete, "get_feature_branch_for_work_request", return_value="feat/WR-999-test"
        ), mock.patch.object(
            undo_complete, "get_worktree_path", return_value="/tmp/some-worktree"
        ):
            existing_branch, existing_wt = undo_complete._check_branch_worktree_clear(
                "WR-999", force=True
            )
            self.assertEqual(existing_branch, "feat/WR-999-test")
            self.assertEqual(existing_wt, "/tmp/some-worktree")

    def test_passes_when_neither_exists(self) -> None:
        """If you don’t have any brand/worktree (None, None) return."""
        with mock.patch.object(
            undo_complete, "get_feature_branch_for_work_request", return_value=None
        ), mock.patch.object(
            undo_complete, "get_worktree_path", return_value=None
        ):
            existing_branch, existing_wt = undo_complete._check_branch_worktree_clear(
                "WR-999", force=False
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

    `main()` The entire flow is worktree manager.create worktree / Director of the Conveyor
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
        with mock.patch.object(undo_complete, "resolve_project_root", return_value=self.repo):
            push_state = undo_complete._detect_push_state(self.merge_commit)
            has_followup = undo_complete._has_followup_commits(self.merge_commit)

            self.assertEqual(push_state, "local")
            self.assertFalse(has_followup)

            # reset
            undo_complete._strategy_reset(self.merge_commit, "WR-999")

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
        with mock.patch.object(undo_complete, "resolve_project_root", return_value=self.repo):
            push_state = undo_complete._detect_push_state(self.merge_commit)
            self.assertEqual(push_state, "pushed")

            # revert
            undo_complete._strategy_revert(self.merge_commit)

            # new HEAD != merge commit (revert commit added)
            new_head = _git_check(self.repo, "rev-parse", "HEAD").stdout.strip()
            self.assertNotEqual(new_head, self.merge_commit)

            # Commit messages include 'Revert'
            log = _git_check(self.repo, "log", "-1", "--format=%s").stdout.strip()
            self.assertIn("Revert", log)


# ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────


class TestCmdCompleteRegressionGuard(unittest.TestCase):
    """WR-906 (Verifying→Complete DnD) cmd complete to change W01 (merge commit storage)
    Unexpected static + validation of operation.

    Verification Point:
      1. FAQ merge commit storage occurs only inside the merge success branch (no influence when merge failed)
      2. FAQ dirty check / Complete guard flow remains true (with guard code in cmd complete source)
      3. FAQs update result call does not break cmd complete itself when wrapping with try/except
    """

    def setUp(self) -> None:
        self.conveyor_cli_path = os.path.join(
            _ENGINE_DIR, "flow", "conveyor_cli.py"
        )
        with open(self.conveyor_cli_path, "r", encoding="utf-8") as f:
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
        # [WARN] output (cmd complete not abort itself)
        self.assertIn("result.merge_commit failed to save", self.source)

    def test_dirty_check_guard_preserved(self) -> None:
        """dirty worktree check code exists in cmd complete (WR-906 protection)."""
        self.assertIn("has_uncommitted_changes(_wt_path)", self.source)
        self.assertIn("Complete Blocks the transition", self.source)

    def test_complete_guard_flow_preserved(self) -> None:
        """Complete Core Flow (find work_request file → update work_request status → Move File)
        This will be maintained.
        """
        # merge commit to enter core flow after saving
        self.assertIn('update_work_request_status(work_request_file, "Complete")', self.source)
        self.assertIn('move_work_request_to_status_dir(work_request_file, "Complete")', self.source)

    def test_update_result_argparse_extension(self) -> None:
        """--merge-commit option added to argparse update-result subdirection."""
        self.assertIn('"--merge-commit"', self.source)
        self.assertIn('dest="merge_commit"', self.source)


# ─ T4.4 Regression verification: work_request repository result fields whitelist ──────────


class TestResultFieldsWhitelist(unittest.TestCase):
    """work_request repository.update result's result fields whitelist
    static verification that contains 'merge commit'.
    """

    def test_merge_commit_in_whitelist(self) -> None:
        from flow import work_request_repository

        # update result's source from result fields tuning
        import inspect
        source = inspect.getsource(work_request_repository.update_result)
        self.assertIn('"merge_commit"', source)

    def test_parse_includes_merge_commit(self) -> None:
        """parse work_request xml also must include the merge commit field to result."""
        from flow import work_request_repository

        import inspect
        source = inspect.getsource(work_request_repository.parse_work_request_xml)
        self.assertIn('"merge_commit"', source)


if __name__ == "__main__":
    unittest.main()
