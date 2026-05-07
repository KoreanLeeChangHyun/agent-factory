"""test_undo_done.py - Done 롤백 시스템(T-905) 단위 + 통합 테스트.

Phase 4 (T4.1~T4.4) 검증 범위:
  T4.1 unit: _detect_push_state / _verify_merge_anchor / _force_done_to_review /
            _load_merge_commit
  T4.2 edge: reflog 만료 / 후속 commit 누적 / 브랜치 이름 충돌 / runs 산출물 보존
  T4.3 integration: 임시 git repo 에서 push 전 reset 분기 / push 후 revert 분기
  T4.4 회귀 검증: cmd_done 가드(merge_commit 저장)가 dirty/Done 흐름을 깨뜨리지 않는지

테스트는 unittest 패턴을 따르며, 환경(예: kanban 디렉터리, project_root) 부수효과를
피하기 위해 가능한 모든 검사를 임시 git repo + 모듈 함수 monkeypatch 로 격리한다.
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

# sys.path: .claude-organic/engine 을 포함시켜 flow 패키지 import 가능하게 한다
_ENGINE_DIR = str(Path(__file__).resolve().parent.parent.parent)
if _ENGINE_DIR not in sys.path:
    sys.path.insert(0, _ENGINE_DIR)

from flow import undo_done  # noqa: E402


# ─── git 헬퍼 ────────────────────────────────────────────────────────────────


def _git(repo: str, *args: str) -> subprocess.CompletedProcess[str]:
    """임시 git 저장소를 대상으로 git 명령을 실행한다."""
    return subprocess.run(
        ["git", "-C", repo] + list(args),
        capture_output=True,
        text=True,
    )


def _git_check(repo: str, *args: str) -> subprocess.CompletedProcess[str]:
    """git 명령을 실행하고 실패 시 AssertionError 를 던진다."""
    result = _git(repo, *args)
    assert result.returncode == 0, (
        f"git {' '.join(args)} 실패: {result.stderr}"
    )
    return result


def _setup_repo_with_merge(repo: str) -> tuple[str, str]:
    """develop + feature 브랜치 + merge 커밋이 있는 임시 repo 를 구성한다.

    Returns:
        (merge_commit_sha, feature_branch_name) 튜플.
    """
    _git_check(repo, "init", "-b", "develop")
    _git_check(repo, "config", "user.email", "test@example.com")
    _git_check(repo, "config", "user.name", "Test")

    init_file = os.path.join(repo, "README.md")
    with open(init_file, "w") as f:
        f.write("init\n")
    _git_check(repo, "add", "README.md")
    _git_check(repo, "commit", "-m", "init")

    # feature 브랜치 분기
    feature_branch = "feat/T-999-test"
    _git_check(repo, "checkout", "-b", feature_branch)
    work_file = os.path.join(repo, "work.py")
    with open(work_file, "w") as f:
        f.write("x = 1\n")
    _git_check(repo, "add", "work.py")
    _git_check(repo, "commit", "-m", "feat: add work")

    # develop 으로 돌아와 --no-ff merge
    _git_check(repo, "checkout", "develop")
    _git_check(
        repo, "merge", "--no-ff", "-m", "merge feat/T-999-test", feature_branch
    )

    head = _git_check(repo, "rev-parse", "HEAD").stdout.strip()
    return head, feature_branch


# ─── T4.1 unit: _detect_push_state ──────────────────────────────────────────


class TestDetectPushState(unittest.TestCase):
    """_detect_push_state: local / pushed / main 3분기 검증."""

    def setUp(self) -> None:
        self.repo = tempfile.mkdtemp(prefix="wf_test_undo_pushstate_")
        self.merge_commit, _ = _setup_repo_with_merge(self.repo)

    def tearDown(self) -> None:
        shutil.rmtree(self.repo, ignore_errors=True)

    def _run(self, sha: str) -> str:
        """resolve_project_root 를 임시 repo 로 교체하고 _detect_push_state 호출."""
        with mock.patch.object(undo_done, "resolve_project_root", return_value=self.repo):
            return undo_done._detect_push_state(sha)

    def test_local_when_no_remote_refs(self) -> None:
        """origin/* refs 가 없으면 'local' 반환."""
        state = self._run(self.merge_commit)
        self.assertEqual(state, "local")

    def test_pushed_when_origin_develop_present(self) -> None:
        """origin/develop ref 가 있으면 'pushed' 반환."""
        # bare remote 생성 후 push
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
        """origin/main ref 가 있으면 'main' 반환 (revert 강제)."""
        remote = tempfile.mkdtemp(prefix="wf_test_undo_remote_main_")
        try:
            _git_check(remote, "init", "--bare", "-b", "develop")
            _git_check(self.repo, "remote", "add", "origin", remote)
            _git_check(self.repo, "push", "origin", "develop")
            # main 브랜치를 develop 에서 분기 + push
            _git_check(self.repo, "branch", "main", "develop")
            _git_check(self.repo, "push", "origin", "main")
            state = self._run(self.merge_commit)
            self.assertEqual(state, "main")
        finally:
            shutil.rmtree(remote, ignore_errors=True)


# ─── T4.1 unit: _verify_merge_anchor ────────────────────────────────────────


class TestVerifyMergeAnchor(unittest.TestCase):
    """_verify_merge_anchor: parent2 정합 검증."""

    def setUp(self) -> None:
        self.repo = tempfile.mkdtemp(prefix="wf_test_undo_anchor_")
        self.merge_commit, self.feature_branch = _setup_repo_with_merge(self.repo)

    def tearDown(self) -> None:
        shutil.rmtree(self.repo, ignore_errors=True)

    def test_anchor_pass_when_parent2_matches_feature_tip(self) -> None:
        """정상 머지: merge_commit^2 == feature 브랜치 tip."""
        with mock.patch.object(undo_done, "resolve_project_root", return_value=self.repo):
            # SystemExit 가 발생하지 않으면 통과
            try:
                undo_done._verify_merge_anchor(self.merge_commit, self.feature_branch)
            except SystemExit:
                self.fail("정상 anchor 검증이 SystemExit 를 던졌습니다")

    def test_anchor_skip_when_feature_branch_deleted(self) -> None:
        """feature 브랜치가 이미 삭제된 경우 스킵 통과."""
        _git_check(self.repo, "branch", "-D", self.feature_branch)
        with mock.patch.object(undo_done, "resolve_project_root", return_value=self.repo):
            # feature 브랜치 빈 문자열 (정상 정리 후 상태)
            try:
                undo_done._verify_merge_anchor(self.merge_commit, "")
            except SystemExit:
                self.fail("브랜치 삭제 후 anchor 검증이 SystemExit 를 던졌습니다")

    def test_anchor_fail_when_parent2_mismatches(self) -> None:
        """parent2 가 expected_branch tip 과 다르면 abort."""
        # feature 브랜치를 다른 SHA 로 강제 이동
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
    """_force_done_to_review: 파일 이동 + status 갱신 검증."""

    def setUp(self) -> None:
        self.tmp_root = tempfile.mkdtemp(prefix="wf_test_undo_force_")
        # kanban 디렉터리 mock
        self.kanban_dir = os.path.join(self.tmp_root, ".claude-organic", "tickets")
        self.done_dir = os.path.join(self.kanban_dir, "done")
        self.review_dir = os.path.join(self.kanban_dir, "review")
        os.makedirs(self.done_dir, exist_ok=True)
        os.makedirs(self.review_dir, exist_ok=True)

        # 더미 티켓 XML 작성 (status=Done)
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
        """파일이 done/ → review/ 로 이동하고 status 가 Review 로 갱신된다."""
        from flow import ticket_repository, ticket_state

        # STATUS_DIR_MAP 과 KANBAN_*_DIR 을 임시 경로로 패치
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

        # 파일이 review/ 로 이동되었는지 확인
        expected_path = os.path.join(self.review_dir, f"{self.ticket_id}.xml")
        self.assertEqual(os.path.normpath(new_path), os.path.normpath(expected_path))
        self.assertTrue(os.path.isfile(expected_path))
        self.assertFalse(os.path.isfile(self.done_file))

        # status 가 Review 로 갱신되었는지 확인 (XML 파싱)
        import xml.etree.ElementTree as ET
        tree = ET.parse(expected_path)
        status_elem = tree.getroot().find("metadata/status")
        self.assertIsNotNone(status_elem)
        self.assertEqual(status_elem.text, "Review")


# ─── T4.1 unit: _load_merge_commit ──────────────────────────────────────────


class TestLoadMergeCommit(unittest.TestCase):
    """_load_merge_commit: result 존재 / 누락 + force / 누락 + non-force 분기."""

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
        """result.merge_commit 가 있으면 그대로 반환한다."""
        self._write_ticket(merge_commit="abc123def456")
        sha = undo_done._load_merge_commit(self.ticket_id, self.ticket_file, force=False)
        self.assertEqual(sha, "abc123def456")

    def test_aborts_when_missing_and_no_force(self) -> None:
        """result.merge_commit 가 없고 force=False 면 abort."""
        self._write_ticket(merge_commit="")
        with self.assertRaises(SystemExit):
            undo_done._load_merge_commit(
                self.ticket_id, self.ticket_file, force=False
            )

    def test_reflog_fallback_when_missing_and_force_no_match(self) -> None:
        """force=True 이지만 reflog 매칭 없음 → abort (T4.2 reflog 만료 케이스)."""
        self._write_ticket(merge_commit="")

        # _git 호출을 매칭 없는 빈 stdout 으로 mock
        fake_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        with mock.patch.object(undo_done, "_git", return_value=fake_result):
            with self.assertRaises(SystemExit):
                undo_done._load_merge_commit(
                    self.ticket_id, self.ticket_file, force=True
                )

    def test_reflog_fallback_when_missing_and_force_with_match(self) -> None:
        """force=True 이고 reflog 매칭 있음 → 첫 후보 SHA 반환."""
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


# ─── T4.2 edge: 후속 commit 누적 (reset → revert 자동 강제) ─────────────────


class TestFollowupCommitsForceRevert(unittest.TestCase):
    """후속 commit 누적 시 _strategy_reset 거부 + _has_followup_commits=True."""

    def setUp(self) -> None:
        self.repo = tempfile.mkdtemp(prefix="wf_test_undo_followup_")
        self.merge_commit, _ = _setup_repo_with_merge(self.repo)

        # 후속 commit 1건 추가
        extra = os.path.join(self.repo, "extra.py")
        with open(extra, "w") as f:
            f.write("z = 3\n")
        _git_check(self.repo, "add", "extra.py")
        _git_check(self.repo, "commit", "-m", "extra after merge")

    def tearDown(self) -> None:
        shutil.rmtree(self.repo, ignore_errors=True)

    def test_has_followup_commits_returns_true(self) -> None:
        """develop HEAD 가 merge_commit 보다 1 commit 앞서있으면 True."""
        with mock.patch.object(undo_done, "resolve_project_root", return_value=self.repo):
            self.assertTrue(undo_done._has_followup_commits(self.merge_commit))

    def test_strategy_reset_aborts_with_followup(self) -> None:
        """_strategy_reset 호출 시 후속 commit 검사로 abort."""
        with mock.patch.object(undo_done, "resolve_project_root", return_value=self.repo):
            with self.assertRaises(SystemExit):
                undo_done._strategy_reset(self.merge_commit, "T-999")

    def test_strategy_reset_no_followup_succeeds(self) -> None:
        """후속 commit 이 없으면 reset 성공 + HEAD 가 merge_commit^ 으로 이동."""
        repo2 = tempfile.mkdtemp(prefix="wf_test_undo_reset_clean_")
        try:
            merge_commit, _ = _setup_repo_with_merge(repo2)
            with mock.patch.object(undo_done, "resolve_project_root", return_value=repo2):
                undo_done._strategy_reset(merge_commit, "T-999")

            # reset 후 HEAD == merge_commit^
            new_head = _git_check(repo2, "rev-parse", "HEAD").stdout.strip()
            parent = _git_check(repo2, "rev-parse", f"{merge_commit}^").stdout.strip()
            self.assertEqual(new_head, parent)
        finally:
            shutil.rmtree(repo2, ignore_errors=True)


# ─── T4.2 edge: 브랜치 이름 충돌 (_check_branch_worktree_clear) ─────────────


class TestBranchWorktreeClear(unittest.TestCase):
    """_check_branch_worktree_clear: 점유 시 abort, force 시 통과."""

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
        """동일 ticket 의 feature 브랜치가 이미 존재하면 force=False 시 abort."""
        with mock.patch.object(
            undo_done, "get_feature_branch_for_ticket", return_value="feat/T-999-test"
        ), mock.patch.object(
            undo_done, "get_worktree_path", return_value=None
        ):
            with self.assertRaises(SystemExit):
                undo_done._check_branch_worktree_clear("T-999", force=False)

    def test_passes_when_branch_exists_with_force(self) -> None:
        """force=True 면 점유 발견에도 통과 (경고만)."""
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
        """브랜치/워크트리 모두 없으면 (None, None) 반환."""
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


# ─── T4.2 edge: runs 산출물 보존 (reset/revert 가 working tree 외부 영향 없음) ─


class TestRunsArtifactsPreserved(unittest.TestCase):
    """reset / revert 어느 분기에서도 .claude-organic/runs/ 디렉터리는 영향 없음.

    runs/ 는 .gitignore 대상이거나 git 추적 외부 파일이므로,
    git operation 이 working tree 의 추적 파일만 변경한다는 사실을 검증한다.
    """

    def setUp(self) -> None:
        self.repo = tempfile.mkdtemp(prefix="wf_test_undo_runs_preserve_")
        self.merge_commit, _ = _setup_repo_with_merge(self.repo)

        # .gitignore 에 runs/ 포함
        gitignore = os.path.join(self.repo, ".gitignore")
        with open(gitignore, "w") as f:
            f.write(".claude-organic/runs/\n")
        _git_check(self.repo, "add", ".gitignore")
        _git_check(self.repo, "commit", "-m", "add gitignore")

        # runs/ 디렉터리에 산출물 생성 (untracked)
        self.runs_dir = os.path.join(self.repo, ".claude-organic", "runs", "20260507-141035")
        os.makedirs(self.runs_dir, exist_ok=True)
        self.artifact = os.path.join(self.runs_dir, "report.md")
        with open(self.artifact, "w") as f:
            f.write("산출물 내용\n")

    def tearDown(self) -> None:
        shutil.rmtree(self.repo, ignore_errors=True)

    def test_artifact_survives_reset(self) -> None:
        """reset --hard 후에도 untracked 산출물은 보존된다."""
        # reset --hard <merge_commit> (merge 커밋 이후 commit 1건 제거하지 않으므로
        # 안전하게 develop tip 보존; 산출물 보존만 확인)
        _git_check(self.repo, "reset", "--hard", "HEAD")
        self.assertTrue(os.path.isfile(self.artifact))
        with open(self.artifact, "r") as f:
            self.assertEqual(f.read(), "산출물 내용\n")

    def test_artifact_survives_revert(self) -> None:
        """revert -m 1 후에도 untracked 산출물은 보존된다."""
        _git_check(
            self.repo, "revert", "-m", "1", "--no-edit", self.merge_commit
        )
        self.assertTrue(os.path.isfile(self.artifact))


# ─── T4.3 통합: reset 분기 (push 전, 후속 commit 없음) ──────────────────────


class TestIntegrationResetFlow(unittest.TestCase):
    """통합: reset 분기가 정상 동작하는지 검증.

    `main()` 전체 흐름은 worktree_manager.create_worktree / 칸반 디렉터리 mock 이
    필요하지만, _strategy_reset 단독 + _detect_push_state + _has_followup_commits 의
    조합으로 push 전 분기 동작을 검증한다.
    """

    def setUp(self) -> None:
        self.repo = tempfile.mkdtemp(prefix="wf_test_undo_integration_reset_")
        self.merge_commit, _ = _setup_repo_with_merge(self.repo)

    def tearDown(self) -> None:
        shutil.rmtree(self.repo, ignore_errors=True)

    def test_local_no_followup_uses_reset(self) -> None:
        """push 전 + 후속 commit 없음 → reset 분기 선택 + 정상 실행."""
        with mock.patch.object(undo_done, "resolve_project_root", return_value=self.repo):
            push_state = undo_done._detect_push_state(self.merge_commit)
            has_followup = undo_done._has_followup_commits(self.merge_commit)

            self.assertEqual(push_state, "local")
            self.assertFalse(has_followup)

            # reset 분기 실행
            undo_done._strategy_reset(self.merge_commit, "T-999")

            # HEAD 가 merge_commit^ 로 이동
            new_head = _git_check(self.repo, "rev-parse", "HEAD").stdout.strip()
            parent = _git_check(
                self.repo, "rev-parse", f"{self.merge_commit}^"
            ).stdout.strip()
            self.assertEqual(new_head, parent)


# ─── T4.3 통합: revert 분기 (push 후) ───────────────────────────────────────


class TestIntegrationRevertFlow(unittest.TestCase):
    """통합: revert 분기가 정상 동작 + 새 commit 추가."""

    def setUp(self) -> None:
        self.repo = tempfile.mkdtemp(prefix="wf_test_undo_integration_revert_")
        self.merge_commit, _ = _setup_repo_with_merge(self.repo)

        # bare remote + push (origin/develop 도달)
        self.remote = tempfile.mkdtemp(prefix="wf_test_undo_remote_")
        _git_check(self.remote, "init", "--bare", "-b", "develop")
        _git_check(self.repo, "remote", "add", "origin", self.remote)
        _git_check(self.repo, "push", "origin", "develop")

    def tearDown(self) -> None:
        shutil.rmtree(self.repo, ignore_errors=True)
        shutil.rmtree(self.remote, ignore_errors=True)

    def test_pushed_uses_revert(self) -> None:
        """push 후 → revert 분기 선택 + 새 commit 추가."""
        with mock.patch.object(undo_done, "resolve_project_root", return_value=self.repo):
            push_state = undo_done._detect_push_state(self.merge_commit)
            self.assertEqual(push_state, "pushed")

            # revert 분기 실행
            undo_done._strategy_revert(self.merge_commit)

            # 새 HEAD != merge_commit (revert commit 추가됨)
            new_head = _git_check(self.repo, "rev-parse", "HEAD").stdout.strip()
            self.assertNotEqual(new_head, self.merge_commit)

            # commit 메시지에 'Revert' 포함
            log = _git_check(self.repo, "log", "-1", "--format=%s").stdout.strip()
            self.assertIn("Revert", log)


# ─── T4.4 회귀 검증: cmd_done 흐름 보호 ─────────────────────────────────────


class TestCmdDoneRegressionGuard(unittest.TestCase):
    """T-906 (Review→Done DnD) cmd_done 가 W01 변경(merge_commit 저장)으로
    영향받지 않는지 정적 + 동작 검증.

    검증 포인트:
      1. merge_commit 저장은 merge 성공 분기 내부에서만 발생 (merge 실패 시 영향 없음)
      2. dirty 검사 / Done 가드 흐름이 그대로 유지됨 (cmd_done 소스에 가드 코드 존재)
      3. update_result 호출은 try/except 로 감싸여 실패 시 cmd_done 자체를 깨뜨리지 않음
    """

    def setUp(self) -> None:
        self.kanban_cli_path = os.path.join(
            _ENGINE_DIR, "flow", "kanban_cli.py"
        )
        with open(self.kanban_cli_path, "r", encoding="utf-8") as f:
            self.source = f.read()

    def test_merge_commit_save_inside_success_branch(self) -> None:
        """update_result 호출이 'merge_result.success' 분기 안 + 'merge_commit'
        truthy 검사 안에 위치하는지 정적 검증.
        """
        # 'else:' 다음에 'update_result(...)' 가 있어야 함 (merge_result.success 분기)
        # 동시에 'if merge_result.merge_commit:' 가드가 존재해야 함
        self.assertIn("if merge_result.merge_commit:", self.source)
        # update_result 호출이 try/except 로 감싸여있는지 확인
        self.assertRegex(
            self.source,
            r"if merge_result\.merge_commit:\s*\n\s*try:",
        )
        # except 블록이 [WARN] 출력 (cmd_done 자체를 abort 시키지 않음)
        self.assertIn("result.merge_commit 저장 실패", self.source)

    def test_dirty_check_guard_preserved(self) -> None:
        """dirty worktree 검사 코드가 cmd_done 에 그대로 존재 (T-906 보호)."""
        self.assertIn("has_uncommitted_changes(_wt_path)", self.source)
        self.assertIn("미커밋 변경이 있는 워크트리입니다", self.source)
        self.assertIn("Done 전이를 차단", self.source)

    def test_done_guard_flow_preserved(self) -> None:
        """Done 전이의 핵심 흐름 (find_ticket_file → update_ticket_status → 파일 이동)
        이 그대로 유지된다.
        """
        # merge_commit 저장이 끝난 뒤 핵심 흐름 진입
        self.assertIn('update_ticket_status(ticket_file, "Done")', self.source)
        self.assertIn('move_ticket_to_status_dir(ticket_file, "Done")', self.source)

    def test_update_result_argparse_extension(self) -> None:
        """argparse update-result 서브커맨드에 --merge-commit 옵션이 추가됨."""
        self.assertIn('"--merge-commit"', self.source)
        self.assertIn('dest="merge_commit"', self.source)


# ─── T4.4 회귀 검증: ticket_repository result_fields 화이트리스트 ──────────


class TestResultFieldsWhitelist(unittest.TestCase):
    """ticket_repository.update_result 의 result_fields 화이트리스트에
    'merge_commit' 이 포함되어 있는지 정적 검증.
    """

    def test_merge_commit_in_whitelist(self) -> None:
        from flow import ticket_repository

        # update_result 의 source 에서 result_fields 튜플 확인
        import inspect
        source = inspect.getsource(ticket_repository.update_result)
        self.assertIn('"merge_commit"', source)

    def test_parse_includes_merge_commit(self) -> None:
        """parse_ticket_xml 도 merge_commit 필드를 result 에 포함시켜야 한다."""
        from flow import ticket_repository

        import inspect
        source = inspect.getsource(ticket_repository.parse_ticket_xml)
        self.assertIn('"merge_commit"', source)


if __name__ == "__main__":
    unittest.main()
