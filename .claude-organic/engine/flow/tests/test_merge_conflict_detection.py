"""test_merge_conflict_detection.py - 병합 충돌 검출 강화 (T-907) 단위 테스트.

검증 범위:
  T1: _detect_conflicts — diff --diff-filter=U 가 충돌 파일을 반환하는 기본 경로
  T2: _detect_conflicts — 1차 빈 결과 시 git status --porcelain fallback
  T3: _detect_conflicts — 두 git 호출 모두 실패 시 sentinel 반환
  T4: cmd_done — conflicts=[] + error_message 에 충돌 패턴 → SystemExit(1)
  T5: cmd_done — 정상 성공 path 가 SystemExit 없이 완료 (회귀 가드)
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

from flow import worktree_manager  # noqa: E402
from flow.worktree_manager import (  # noqa: E402
    _detect_conflicts,
    _parse_porcelain_conflicts,
    _SENTINEL_UNKNOWN_CONFLICT,
)


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


def _setup_conflict_repo(repo: str) -> str:
    """develop + feature 브랜치에서 동일 라인 충돌이 발생한 임시 repo 를 구성한다.

    - develop: work.py 의 첫 줄을 'x = "develop"\n' 으로 변경 + commit
    - feature: 같은 줄을 'x = "feature"\n' 으로 변경 + commit
    - develop 에서 git merge feature (충돌 상태, resolve 하지 않음)

    Returns:
        feature 브랜치 이름.
    """
    _git_check(repo, "init", "-b", "develop")
    _git_check(repo, "config", "user.email", "test@example.com")
    _git_check(repo, "config", "user.name", "Test")

    work_file = os.path.join(repo, "work.py")
    with open(work_file, "w") as f:
        f.write('x = "base"\n')
    _git_check(repo, "add", "work.py")
    _git_check(repo, "commit", "-m", "init")

    # feature 브랜치: 같은 라인 수정
    feature_branch = "feat/T-907-test"
    _git_check(repo, "checkout", "-b", feature_branch)
    with open(work_file, "w") as f:
        f.write('x = "feature"\n')
    _git_check(repo, "add", "work.py")
    _git_check(repo, "commit", "-m", "feat: change x")

    # develop 으로 돌아와 같은 라인 수정
    _git_check(repo, "checkout", "develop")
    with open(work_file, "w") as f:
        f.write('x = "develop"\n')
    _git_check(repo, "add", "work.py")
    _git_check(repo, "commit", "-m", "develop: change x")

    # merge 시도 — 충돌 발생 (비정상 returncode 는 무시)
    subprocess.run(
        ["git", "-C", repo, "merge", "--no-ff", feature_branch],
        capture_output=True,
        text=True,
    )

    return feature_branch


# ─── T1: _detect_conflicts diff --diff-filter=U 기본 경로 ────────────────────


class TestDetectConflictsDiffFilterPopulates(unittest.TestCase):
    """_detect_conflicts 가 diff --diff-filter=U 에서 충돌 파일을 정확히 반환한다."""

    def setUp(self) -> None:
        self.repo = tempfile.mkdtemp(prefix="wf_test_t907_conflict_")
        _setup_conflict_repo(self.repo)

    def tearDown(self) -> None:
        shutil.rmtree(self.repo, ignore_errors=True)

    def test_detect_conflicts_diff_filter_populates(self) -> None:
        """임시 repo 에서 충돌 발생 후 _detect_conflicts 가 충돌 파일을 반환한다."""
        conflicts = _detect_conflicts(repo_path=self.repo)
        # sentinel 이 아니어야 하며, work.py 가 포함되어야 한다
        self.assertNotIn(_SENTINEL_UNKNOWN_CONFLICT, conflicts)
        self.assertIn("work.py", conflicts)


# ─── T2: _detect_conflicts porcelain fallback ────────────────────────────────


class TestDetectConflictsPorcelainFallback(unittest.TestCase):
    """1차(diff --diff-filter=U) 결과가 빈 리스트일 때 porcelain fallback 으로 충돌 파일을 반환한다."""

    def _make_completed(
        self, returncode: int, stdout: str
    ) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(
            args=[], returncode=returncode, stdout=stdout, stderr=""
        )

    def test_detect_conflicts_porcelain_fallback(self) -> None:
        """diff filter 가 빈 stdout 반환 시 porcelain 결과로 충돌 파일을 반환한다."""
        call_count = 0

        def fake_git(*args: str, repo_path=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # 1차: diff --name-only --diff-filter=U → 빈 결과
                return self._make_completed(0, "")
            else:
                # 2차: status --porcelain → UU 코드 포함
                return self._make_completed(0, "UU work.py\n")

        with mock.patch.object(worktree_manager, "_git", side_effect=fake_git):
            conflicts = _detect_conflicts()

        self.assertEqual(conflicts, ["work.py"])


# ─── T3: _detect_conflicts sentinel on both failure ──────────────────────────


class TestDetectConflictsSentinelOnFailure(unittest.TestCase):
    """두 git 호출이 모두 실패(returncode != 0) 시 sentinel 을 반환한다."""

    def _make_failed(self) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="fatal: not a git repo"
        )

    def test_detect_conflicts_sentinel_on_failure(self) -> None:
        """두 호출 모두 실패 시 ['<unknown-conflict>'] sentinel 반환."""
        with mock.patch.object(worktree_manager, "_git", return_value=self._make_failed()):
            conflicts = _detect_conflicts()

        self.assertEqual(conflicts, [_SENTINEL_UNKNOWN_CONFLICT])


# ─── T4: cmd_done — 빈 conflicts + error_message 충돌 패턴 → SystemExit ───────


class TestCmdDoneExitsOnEmptyConflictsWithSignalMessage(unittest.TestCase):
    """merge_result.success=False + conflicts=[] + error_message 에 '병합 충돌' 포함 시
    cmd_done 이 SystemExit(1) 을 발생시킨다.
    """

    def test_cmd_done_exits_on_empty_conflicts_with_signal_message(self) -> None:
        """conflicts 빈 리스트이지만 error_message 에 충돌 패턴 있으면 SystemExit."""
        from flow import kanban_cli
        from flow.worktree_manager import MergeResult

        # merge_to_develop 이 충돌 실패를 반환하도록 monkeypatch
        fake_merge_result = MergeResult(
            success=False,
            merge_commit="",
            merged_branch="feat/T-907-test",
            conflicts=[],
            error_message="병합 충돌 발생: work.py 에서 충돌이 감지되었습니다",
        )

        with mock.patch.object(
            kanban_cli, "find_ticket_file", return_value="/tmp/fake/T-907.xml"
        ), mock.patch(
            "flow.worktree_manager.is_worktree_enabled", return_value=True
        ), mock.patch(
            "flow.worktree_manager.get_worktree_path", return_value="/tmp/fake-worktree"
        ), mock.patch(
            "flow.worktree_manager.has_uncommitted_changes", return_value=False
        ), mock.patch(
            "flow.worktree_manager.merge_to_develop", return_value=fake_merge_result
        ), mock.patch(
            "flow.branch_strategy.get_feature_branch_for_ticket",
            return_value="feat/T-907-test",
        ):
            with self.assertRaises(SystemExit) as ctx:
                kanban_cli.cmd_done("T-907")

        self.assertEqual(ctx.exception.code, 1)


# ─── T5: cmd_done — 정상 성공 path 는 SystemExit 없이 완료 (회귀 가드) ─────────


class TestCmdDoneProceedsOnSuccess(unittest.TestCase):
    """merge_to_develop 성공 시 cmd_done 이 SystemExit 없이 Done 전이를 완료한다."""

    def setUp(self) -> None:
        # 실제 티켓 파일을 임시 디렉터리에 생성
        self.tmp_dir = tempfile.mkdtemp(prefix="wf_test_t907_done_success_")
        self.done_dir = os.path.join(self.tmp_dir, "done")
        self.review_dir = os.path.join(self.tmp_dir, "review")
        os.makedirs(self.review_dir, exist_ok=True)
        os.makedirs(self.done_dir, exist_ok=True)

        # Review 상태 티켓 XML 생성
        self.ticket_id = "T-907"
        self.ticket_file = os.path.join(self.review_dir, f"{self.ticket_id}.xml")
        with open(self.ticket_file, "w", encoding="utf-8") as f:
            f.write(
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                "<ticket>\n"
                "  <metadata>\n"
                f"    <number>{self.ticket_id}</number>\n"
                "    <title>test ticket</title>\n"
                "    <created>2026-05-07 12:00:00</created>\n"
                "    <updated>2026-05-07 12:00:00</updated>\n"
                "    <status>Review</status>\n"
                "    <command>implement</command>\n"
                "  </metadata>\n"
                "  <prompt />\n"
                "  <result />\n"
                "</ticket>\n"
            )

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_cmd_done_proceeds_on_success(self) -> None:
        """merge_to_develop 성공 반환 시 cmd_done 이 Done 전이를 완료한다."""
        from flow import kanban_cli
        from flow import ticket_repository, ticket_state
        from flow.worktree_manager import MergeResult

        fake_merge_result = MergeResult(
            success=True,
            merge_commit="abc12345def67890",
            merged_branch="feat/T-907-test",
            conflicts=[],
            error_message="",
        )

        patched_status_map = dict(ticket_repository.STATUS_DIR_MAP)
        patched_status_map["Review"] = self.review_dir
        patched_status_map["Done"] = self.done_dir

        with mock.patch.object(
            ticket_repository, "STATUS_DIR_MAP", patched_status_map
        ), mock.patch.object(
            ticket_repository, "KANBAN_REVIEW_DIR", self.review_dir
        ), mock.patch.object(
            ticket_repository, "KANBAN_DONE_DIR", self.done_dir
        ), mock.patch.object(
            kanban_cli, "find_ticket_file", return_value=self.ticket_file
        ), mock.patch(
            "flow.worktree_manager.is_worktree_enabled", return_value=True
        ), mock.patch(
            "flow.worktree_manager.get_worktree_path", return_value="/tmp/fake-worktree"
        ), mock.patch(
            "flow.worktree_manager.has_uncommitted_changes", return_value=False
        ), mock.patch(
            "flow.worktree_manager.merge_to_develop", return_value=fake_merge_result
        ), mock.patch(
            "flow.branch_strategy.get_feature_branch_for_ticket",
            return_value="feat/T-907-test",
        ), mock.patch.object(
            kanban_cli, "update_result", return_value=None
        ), mock.patch.object(
            ticket_state, "validate_transition", return_value=None
        ):
            # SystemExit 없이 완료되어야 한다
            try:
                kanban_cli.cmd_done(self.ticket_id)
            except SystemExit as e:
                self.fail(f"cmd_done 이 예기치 않은 SystemExit({e.code}) 를 발생시켰습니다")


if __name__ == "__main__":
    unittest.main()
