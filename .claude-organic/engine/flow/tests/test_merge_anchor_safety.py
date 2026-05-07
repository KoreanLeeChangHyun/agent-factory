"""test_merge_anchor_safety.py - merge anchor 안전성 회귀 가드 테스트 (T-410).

검증 범위:
  T1: already-up-to-date / ff skip —
      feature 가 develop 의 ancestor 인 임시 repo 에서
      _stage2_5_verify_merge_anchor 호출 → True 반환 + "skip" 로그 + reset 미호출 확인.

  T2: non-ff 정상 통과 —
      feature 가 develop 에서 분기된 임시 repo 에서 non-ff merge commit 생성 후
      _stage2_5_verify_merge_anchor 호출 → True 반환 + reset 미호출 확인.
      merge_commit^2 == feature HEAD SHA 를 검증한다.

  T3: non-ff 검증 실패 후 롤백 (T-403 회귀 가드) —
      develop 에 사전 ahead commit 2개 + feature 분기 + non-ff merge 후
      mock 으로 _git 의 ^2 결과를 변조하여 anchor 검증 실패를 강제.
      _stage2_5_verify_merge_anchor 가 False 반환 + _handle_anchor_failure 가
      git reset --hard <pre_merge_develop_sha> 호출 + 사전 ahead commit 2개가
      develop log 에 보존되는지 확인한다.

  T4: HEAD^ fallback —
      pre_merge_develop_sha="" 로 _handle_anchor_failure 호출 시
      기존 HEAD^ 경로로 fallback + 경고 로그 출력 확인.
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

import flow.merge_pipeline as _mp  # noqa: E402


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


def _setup_base_repo(repo: str) -> None:
    """공통 기반 repo 초기화: init + user config + base commit."""
    _git_check(repo, "init", "-b", "develop")
    _git_check(repo, "config", "user.email", "test@example.com")
    _git_check(repo, "config", "user.name", "Test")

    work_file = os.path.join(repo, "work.py")
    with open(work_file, "w") as f:
        f.write('x = "base"\n')
    _git_check(repo, "add", "work.py")
    _git_check(repo, "commit", "-m", "init")


def _get_head_sha(repo: str) -> str:
    """현재 develop HEAD SHA 를 반환한다."""
    result = _git(repo, "rev-parse", "HEAD")
    assert result.returncode == 0
    return result.stdout.strip()


def _get_log_shas(repo: str, n: int = 10) -> list[str]:
    """develop log 에서 최근 n 개 commit SHA 를 반환한다 (newest first)."""
    result = _git(repo, "log", "--format=%H", f"-{n}")
    assert result.returncode == 0
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


# ─── T1: already-up-to-date / ff skip ────────────────────────────────────────


class TestVerifyMergeAnchorAlreadyUpToDateSkip(unittest.TestCase):
    """feature 가 develop ancestor 인 경우 anchor 검증이 skip 되어야 한다.

    시나리오: feature 브랜치가 develop 에 이미 포함된 상태에서
    git merge --no-ff 를 호출하면 "Already up to date." 가 반환되고
    새 merge commit 이 생성되지 않는다. 이 때 merge_commit == pre_merge_develop_sha
    이므로 _stage2_5_verify_merge_anchor 는 True 를 반환해야 한다.
    """

    def setUp(self) -> None:
        self.repo = tempfile.mkdtemp(prefix="wf_test_t410_t1_")
        _setup_base_repo(self.repo)

        # feature 브랜치 생성 후 commit (develop 에 포함됨)
        self.feature_branch = "feat/T-410-t1-test"
        _git_check(self.repo, "checkout", "-b", self.feature_branch)
        work_file = os.path.join(self.repo, "work.py")
        with open(work_file, "w") as f:
            f.write('x = "feature"\n')
        _git_check(self.repo, "add", "work.py")
        _git_check(self.repo, "commit", "-m", "feat: add feature commit")

        # develop 으로 돌아와 feature 커밋을 fast-forward 로 포함
        _git_check(self.repo, "checkout", "develop")
        _git_check(self.repo, "merge", "--ff-only", self.feature_branch)

        # 이제 feature 는 develop 의 ancestor → git merge --no-ff 는 up-to-date
        self.pre_merge_sha = _get_head_sha(self.repo)
        merge_result = _git(
            self.repo, "merge", "--no-ff", self.feature_branch
        )
        # "Already up to date." — merge_commit == develop HEAD == pre_merge_sha
        self.merge_commit = _get_head_sha(self.repo)
        self.assertEqual(
            self.merge_commit,
            self.pre_merge_sha,
            "already-up-to-date 케이스에서 HEAD 가 변해서는 안 된다",
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.repo, ignore_errors=True)

    def test_already_up_to_date_returns_true_and_no_reset(self) -> None:
        """already-up-to-date 케이스에서 True 반환 + reset 미호출."""
        # _git 을 repo 경로로 패치하고, is_worktree_enabled 를 True 로 강제한다.
        # _stage2_5_verify_merge_anchor 내부의 _git 호출은 실제 repo 를 향하도록
        # repo_path 를 주입한다.
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

        self.assertTrue(result, "_stage2_5_verify_merge_anchor 는 True 를 반환해야 한다")

        # "skip" 관련 로그가 출력되어야 한다
        all_output = "\n".join(printed_lines)
        self.assertIn(
            "already-up-to-date",
            all_output,
            "already-up-to-date skip 로그가 출력되어야 한다",
        )

        # develop HEAD 가 변하지 않아야 한다 (reset 미호출 확인)
        head_after = _get_head_sha(self.repo)
        self.assertEqual(
            head_after,
            self.pre_merge_sha,
            "reset 이 호출되어 HEAD 가 변경되어서는 안 된다",
        )


# ─── T2: non-ff 정상 통과 ────────────────────────────────────────────────────


class TestVerifyMergeAnchorNonFfPass(unittest.TestCase):
    """feature 가 develop 에서 분기되어 non-ff merge commit 이 생성된 경우
    anchor 검증이 정상 통과 (True) 해야 한다.

    검증 포인트:
      - merge_commit^2 == feature HEAD SHA
      - _stage2_5_verify_merge_anchor → True
      - reset 미호출 (develop HEAD 보존)
    """

    def setUp(self) -> None:
        self.repo = tempfile.mkdtemp(prefix="wf_test_t410_t2_")
        _setup_base_repo(self.repo)

        # feature 브랜치 생성 및 commit
        self.feature_branch = "feat/T-410-t2-test"
        _git_check(self.repo, "checkout", "-b", self.feature_branch)
        work_file = os.path.join(self.repo, "work.py")
        with open(work_file, "a") as f:
            f.write('y = "feature"\n')
        _git_check(self.repo, "add", "work.py")
        _git_check(self.repo, "commit", "-m", "feat: add y")
        self.feature_head_sha = _get_head_sha(self.repo)

        # develop 으로 돌아와 non-ff merge.
        # develop 에 별도 commit 을 추가하지 않는다.
        # 이유: git diff merge_commit^2 merge_commit 검증(검증 2)은
        # "feature HEAD → merge commit 사이의 diff" 를 보는데,
        # develop 에 추가 변경이 있으면 그 변경이 diff 에 포함되어
        # non-empty → 검증 실패가 된다. 정상 non-ff merge 임에도 불구하고.
        # non-ff merge 구조(merge commit 에 ^2 부모 존재) 는 develop 에 별도
        # commit 이 없어도 --no-ff 플래그로 강제 생성 가능하다.
        _git_check(self.repo, "checkout", "develop")

        # pre_merge SHA 기록 후 non-ff merge
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
        """non-ff merge commit 후 anchor 검증 통과 + reset 미호출."""
        # ^2 SHA == feature HEAD SHA 사전 확인
        parent2_result = _git(self.repo, "rev-parse", f"{self.merge_commit}^2")
        self.assertEqual(parent2_result.returncode, 0)
        self.assertEqual(
            parent2_result.stdout.strip(),
            self.feature_head_sha,
            "merge_commit^2 는 feature HEAD SHA 와 일치해야 한다",
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

        self.assertTrue(result, "anchor 검증은 통과 (True) 해야 한다")

        # develop HEAD 가 변하지 않아야 한다
        head_after = _get_head_sha(self.repo)
        self.assertEqual(
            head_after,
            self.merge_commit,
            "정상 통과 시 HEAD 는 merge_commit 이어야 한다",
        )


# ─── T3: non-ff 검증 실패 후 롤백 (T-403 회귀 가드) ─────────────────────────


class TestVerifyMergeAnchorRollbackPreservesAheadCommits(unittest.TestCase):
    """anchor 검증 실패 시 롤백이 pre_merge_develop_sha 로 수행되어
    develop 의 사전 ahead commit 이 보존되어야 한다 (T-403 회귀 가드).

    시나리오:
      1. develop 에 ahead commit 2개 추가 (a1, a2)
      2. feature 브랜치 분기 + commit
      3. develop 에서 non-ff merge → merge_commit 생성
      4. mock 으로 ^2 rev-parse 결과를 가짜 SHA 로 변조
         → anchor 검증 실패 강제
      5. _stage2_5_verify_merge_anchor → False 반환 확인
      6. git reset --hard pre_merge_develop_sha (== a2) 호출 확인
      7. develop log 에 a1, a2 가 보존 확인
    """

    def setUp(self) -> None:
        self.repo = tempfile.mkdtemp(prefix="wf_test_t410_t3_")
        _setup_base_repo(self.repo)

        # develop 에 사전 ahead commit 2개 추가
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

        # feature 브랜치 생성 및 commit
        self.feature_branch = "feat/T-410-t3-test"
        _git_check(self.repo, "checkout", "-b", self.feature_branch)
        feat_file = os.path.join(self.repo, "feat.py")
        with open(feat_file, "w") as f:
            f.write('feat = "T-410"\n')
        _git_check(self.repo, "add", "feat.py")
        _git_check(self.repo, "commit", "-m", "feat: add feat.py")
        self.feature_head_sha = _get_head_sha(self.repo)

        # develop 로 복귀 후 non-ff merge
        _git_check(self.repo, "checkout", "develop")
        self.pre_merge_sha = _get_head_sha(self.repo)
        self.assertEqual(
            self.pre_merge_sha,
            self.ahead2_sha,
            "pre_merge_sha 는 ahead2 여야 한다",
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
        """anchor 검증 실패 → False 반환 + reset to pre_merge_sha + ahead commits 보존."""
        orig_git = _mp._git
        fake_sha = "deadbeef" * 5  # 40자 가짜 SHA

        def patched_git(*args, repo_path=None):
            # ^2 rev-parse 호출만 변조하여 anchor 검증 실패 강제
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

        self.assertFalse(result, "anchor 검증 실패 시 False 를 반환해야 한다")

        # rollback 후 HEAD 확인: pre_merge_sha (== ahead2) 로 되돌아가야 한다
        head_after = _get_head_sha(self.repo)
        self.assertEqual(
            head_after,
            self.pre_merge_sha,
            f"롤백 후 HEAD 는 pre_merge_sha({self.pre_merge_sha[:8]}) 여야 한다",
        )

        # 사전 ahead commit 2개 (ahead1, ahead2) 가 log 에 보존되어야 한다
        log_shas = _get_log_shas(self.repo, n=10)
        self.assertIn(
            self.ahead1_sha,
            log_shas,
            "ahead1 commit 이 develop log 에 보존되어야 한다",
        )
        self.assertIn(
            self.ahead2_sha,
            log_shas,
            "ahead2 commit 이 develop log 에 보존되어야 한다",
        )


# ─── T4: HEAD^ fallback ───────────────────────────────────────────────────────


class TestHandleAnchorFailureHeadCaretFallback(unittest.TestCase):
    """pre_merge_develop_sha="" 로 _handle_anchor_failure 호출 시
    HEAD^ fallback 경로로 reset + 경고 로그 출력 확인.

    검증 포인트:
      - reset 호출 대상이 "HEAD^" (빈 pre_merge_develop_sha 케이스)
      - _error 로 fallback 경고 메시지 출력
    """

    def setUp(self) -> None:
        self.repo = tempfile.mkdtemp(prefix="wf_test_t410_t4_")
        _setup_base_repo(self.repo)

        # non-ff merge commit 을 하나 생성해서 HEAD^ 가 유효하게 만든다
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
        """pre_merge_develop_sha 빈 문자열 → HEAD^ fallback + 경고 로그."""
        orig_git = _mp._git

        def patched_git(*args, repo_path=None):
            return orig_git(*args, repo_path=self.repo)

        error_messages: list[str] = []

        def fake_error(msg: str) -> None:
            error_messages.append(msg)

        with mock.patch.object(_mp, "_git", side_effect=patched_git), mock.patch.object(
            _mp, "_error", side_effect=fake_error
        ):
            # pre_merge_develop_sha="" → HEAD^ fallback 경로
            _mp._handle_anchor_failure(
                merge_commit=self.merge_commit,
                feature_branch=self.feature_branch,
                reason="T4 test: forced failure",
                pre_merge_develop_sha="",
            )

        # fallback 경고 로그 확인
        all_errors = "\n".join(error_messages)
        self.assertIn(
            "HEAD^",
            all_errors,
            "HEAD^ fallback 경고 메시지가 출력되어야 한다",
        )

        # HEAD^ 로 rollback 됐으면 develop HEAD 는 pre_merge_sha 여야 한다
        head_after = _get_head_sha(self.repo)
        self.assertEqual(
            head_after,
            self.pre_merge_sha,
            "HEAD^ rollback 후 develop HEAD 는 pre_merge_sha 여야 한다",
        )


if __name__ == "__main__":
    unittest.main()
