"""test_undo_redo_cycle.py - T-441 Done 롤백 + 재머지 통합 회귀 테스트.

W05 본격 통합 회귀 테스트. W03 가 추가한 단위 가드(`_stage1_5_premerge_state_guard`)
를 더 큰 사이클(Done 롤백 → 워크트리 재생성 → 재머지) 안에서 검증한다.

회귀 박제 (T-440 사례, 2026-05-08):
  1. flow-merge 가 feat/T-440 을 develop 에 정상 머지 (51555f3)
  2. undo_done.py:_strategy_reset 이 develop 을 51555f3^ (= ba74608) 로 reset
  3. 워크트리/feature 브랜치 재생성됐으나 변경분 없음 (빈 브랜치)
  4. develop 위로 별건 revert commit (6efc6ef) 가 추가됨
  5. flow-merge --force 로 재머지 시도 → anchor 검증 실패
  6. _handle_anchor_failure 가 reset --hard pre_merge_develop_sha (= 6efc6ef)
     실행 → 별건 revert commit 까지 함께 사라지지는 않으나 변경분 소실
  7. 사용자가 a74fb7a 로 수동 복구

본 테스트는 위 사이클 각 분기를 격리된 임시 git repo 안에서 시뮬레이션하여
W03 가드가 차단하는 케이스 / 통과시키는 케이스를 모두 회귀 0 으로 묶는다.

검증 시나리오:
  S1 (정상 경로 / T-906): force 미체크 + 변경분 있는 워크트리/브랜치
      → Stage 1.5 가드 통과 + Stage 2.5 anchor 검증 통과
      → develop HEAD = 머지 commit
  S2 (force + 부재 / 안내 안내): force 체크 + 워크트리/브랜치 부재
      → 가드 차단 + reflog fallback 안내 메시지 노출 (자동 적용 X)
      → develop HEAD 변동 0
  S3 (음성 / 일반): force 미체크 + 워크트리/브랜치 부재
      → 가드 차단 + 명확한 에러 메시지
      → 빈 머지 0건, develop HEAD 변동 0
  S4 (T-905 정상): undo_done push 전 reset 시뮬레이션
      → develop HEAD = merge_commit^ (별건 commit 손실 0)
  S5 (T-906 정상 후속): 워크트리에 변경분 commit 후 재머지
      → develop HEAD 정합 (merge commit + ahead commits 보존)
  S6 (T-440 회귀 차단 advisory): 별건 commit 위에서 빈 브랜치 머지 시도
      → Stage 1.5 가드 차단 (anchor 단계 도달 전 차단됨)
      또한 `_handle_anchor_failure` 직접 호출 시 parent1_mismatch advisory 발동

테스트는 unittest 기반으로 기존 `test_premerge_state_guard.py`,
`test_merge_anchor_safety.py` 의 fixture 패턴과 일관성을 유지한다.
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
    """공통 기반 repo 초기화: init + user config + base commit on develop."""
    _git_check(repo, "init", "-b", "develop")
    _git_check(repo, "config", "user.email", "test@example.com")
    _git_check(repo, "config", "user.name", "Test")

    work_file = os.path.join(repo, "work.py")
    with open(work_file, "w") as f:
        f.write('x = "base"\n')
    _git_check(repo, "add", "work.py")
    _git_check(repo, "commit", "-m", "init")


def _head_sha(repo: str, ref: str = "HEAD") -> str:
    """ref 가 가리키는 SHA 를 반환한다."""
    result = _git_check(repo, "rev-parse", ref)
    return result.stdout.strip()


def _log_shas(repo: str, n: int = 20) -> list[str]:
    """develop log SHA 목록 (newest first)."""
    result = _git_check(repo, "log", "--format=%H", f"-{n}")
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _commit_on(repo: str, branch: str, filename: str, content: str, msg: str) -> str:
    """branch 위에 파일 commit 후 SHA 반환. branch 가 없으면 분기 생성."""
    # 현재 브랜치 확인
    cur = _git_check(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    if cur != branch:
        # 브랜치 존재 여부 확인
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


# ─── 공통 베이스 ─────────────────────────────────────────────────────────────


class _CycleTestBase(unittest.TestCase):
    """모든 사이클 시나리오의 공통 setUp/tearDown.

    각 테스트는 격리된 임시 git repo 에서 develop + feat/T-441-* 브랜치를
    생성하며, _mp._git 호출을 임시 repo 로 라우팅하는 patched_git fixture 를
    제공한다.
    """

    ticket: str = "T-441"
    feature_branch: str = "feat/T-441-cycle"

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
        """develop 분기 후 feature 브랜치에 변경분 1개 commit. SHA 반환."""
        target = branch or self.feature_branch
        _git_check(self.repo, "checkout", "develop")
        _git_check(self.repo, "checkout", "-b", target)
        feat_path = os.path.join(self.repo, filename)
        with open(feat_path, "w") as f:
            f.write(content)
        _git_check(self.repo, "add", filename)
        _git_check(self.repo, "commit", "-m", f"feat({self.ticket}): add {filename}")
        sha = _head_sha(self.repo)
        _git_check(self.repo, "checkout", "develop")
        return sha

    def _make_empty_feature(self, branch: str | None = None) -> None:
        """develop 분기 직후 변경 없이 feature 브랜치만 생성 (T-440 회귀 시뮬)."""
        target = branch or self.feature_branch
        _git_check(self.repo, "branch", target, "develop")

    def _add_unrelated_commit_on_develop(
        self, filename: str = "unrelated.py", content: str = "u = 1\n"
    ) -> str:
        """develop 위에 별건 commit 추가 후 SHA 반환 (T-440 의 6efc6ef 시뮬)."""
        _git_check(self.repo, "checkout", "develop")
        fpath = os.path.join(self.repo, filename)
        with open(fpath, "w") as f:
            f.write(content)
        _git_check(self.repo, "add", filename)
        _git_check(self.repo, "commit", "-m", "chore: unrelated revert-style commit")
        return _head_sha(self.repo)

    def _non_ff_merge(self, branch: str | None = None) -> str:
        """develop 으로 checkout 후 branch 를 --no-ff 머지. merge commit SHA 반환."""
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


# ─── S1: 정상 경로 (force 미체크 + 변경분 있는 워크트리/브랜치) ─────────────


class TestScenario1NormalPath(_CycleTestBase):
    """S1 — 정상 경로 (T-906 Review→Done DnD 동등).

    검증:
      - Stage 1.5 가드 통과 (commits ahead > 0)
      - non-ff 머지 후 anchor 검증 통과
      - develop HEAD == merge commit
    """

    def test_normal_merge_passes_guard_and_anchor(self) -> None:
        feature_sha = self._make_feature_with_change()
        pre_merge_sha = _head_sha(self.repo, "develop")

        # Stage 1.5 가드 통과 검증
        with mock.patch(
            "flow.branch_strategy.get_feature_branch_for_ticket",
            return_value=self.feature_branch,
        ), mock.patch.object(_mp, "_git", side_effect=self._patched_git()):
            ok, msg = _mp._stage1_5_premerge_state_guard(
                self.ticket, worktree_path=self.repo, force=False
            )
        self.assertTrue(ok, f"S1 가드는 통과해야 한다 (msg={msg})")
        self.assertEqual(msg, "")

        # non-ff 머지 후 anchor 검증 통과
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
        self.assertTrue(anchor_ok, "S1 anchor 검증은 통과해야 한다")

        # develop HEAD = merge commit (변동 없음)
        self.assertEqual(
            _head_sha(self.repo, "develop"),
            merge_commit,
            "S1 정상 머지 후 develop HEAD 는 merge commit 이어야 한다",
        )

        # feature 브랜치 변경분이 develop log 에 도달 가능
        log = _log_shas(self.repo, n=10)
        self.assertIn(feature_sha, log, "feature commit 이 develop 에 보존되어야 한다")


# ─── S2: force + 워크트리/브랜치 부재 (advisory 안내) ─────────────────────────


class TestScenario2ForceAbsentReflogAdvisory(_CycleTestBase):
    """S2 — force=True + 워크트리/브랜치 부재.

    회귀 박제: T-440 사례에서 사용자가 빈 워크트리·브랜치 상태로 재머지 시도 시
    가드가 차단하지 않으면 빈 머지 + reset --hard 별건 commit 위치로 손실 발생.
    W03 정책: force=True 라도 자동 트리거 금지 + reflog fallback 안내만 노출.

    검증:
      - 가드 차단 (False 반환) + 안내 메시지 노출
      - develop HEAD 변동 0
    """

    def test_force_with_branch_absent_blocks_with_advisory(self) -> None:
        pre_merge_sha = _head_sha(self.repo, "develop")

        captured_stderr: list[str] = []

        def fake_print(*args, **kwargs):
            if kwargs.get("file") is sys.stderr:
                captured_stderr.append(" ".join(str(a) for a in args))

        with mock.patch(
            "flow.branch_strategy.get_feature_branch_for_ticket",
            return_value=None,  # 브랜치 unresolved
        ), mock.patch.object(
            _mp, "_git", side_effect=self._patched_git()
        ), mock.patch("builtins.print", side_effect=fake_print):
            ok, msg = _mp._stage1_5_premerge_state_guard(
                self.ticket, worktree_path=None, force=True
            )

        self.assertFalse(ok, "force 라도 브랜치 부재는 차단되어야 한다")
        self.assertIn("부재", msg)

        # advisory 메시지 노출 (reflog 안내 키워드)
        all_stderr = "\n".join(captured_stderr)
        self.assertIn(
            "reflog",
            all_stderr.lower(),
            "force 모드에서 reflog fallback 안내가 노출되어야 한다",
        )

        # develop HEAD 변동 0 (reset/머지 자동 트리거 금지)
        self.assertEqual(
            _head_sha(self.repo, "develop"),
            pre_merge_sha,
            "S2 가드 차단 시 develop HEAD 가 변경되어서는 안 된다",
        )


# ─── S3: 음성 (force 미체크 + 부재) ───────────────────────────────────────────


class TestScenario3NormalAbsentBlocked(_CycleTestBase):
    """S3 — 음성 시나리오 (force 미체크 + 워크트리/브랜치 부재).

    검증:
      - 가드 차단 + 명확한 에러 메시지
      - 빈 머지 0건 / develop HEAD 변동 0
    """

    def test_no_force_with_branch_absent_blocks_clearly(self) -> None:
        pre_merge_sha = _head_sha(self.repo, "develop")
        log_shas_before = _log_shas(self.repo, n=20)

        error_messages: list[str] = []

        def fake_error(msg: str) -> None:
            error_messages.append(msg)

        with mock.patch(
            "flow.branch_strategy.get_feature_branch_for_ticket",
            return_value=None,
        ), mock.patch.object(
            _mp, "_git", side_effect=self._patched_git()
        ), mock.patch.object(_mp, "_error", side_effect=fake_error):
            ok, msg = _mp._stage1_5_premerge_state_guard(
                self.ticket, worktree_path=None, force=False
            )

        self.assertFalse(ok, "force 미체크 + 부재는 차단되어야 한다")
        self.assertIn("부재", msg)

        # 명확한 에러 메시지 발행 확인
        all_errors = "\n".join(error_messages)
        self.assertIn("[GUARD]", all_errors, "가드 식별자가 에러에 포함되어야 한다")

        # develop HEAD 변동 0
        self.assertEqual(
            _head_sha(self.repo, "develop"),
            pre_merge_sha,
            "S3 가드 차단 시 develop HEAD 가 변경되어서는 안 된다",
        )

        # 빈 머지 0건 — develop log 가 동일해야 한다
        self.assertEqual(
            _log_shas(self.repo, n=20),
            log_shas_before,
            "S3 가드 차단 시 develop log 에 새로운 commit 이 추가되어서는 안 된다",
        )

    def test_no_force_with_empty_branch_blocks(self) -> None:
        """존재하지만 변경분 0 인 빈 브랜치도 차단 (T-440 회귀 핵심)."""
        self._make_empty_feature()
        pre_merge_sha = _head_sha(self.repo, "develop")

        with mock.patch(
            "flow.branch_strategy.get_feature_branch_for_ticket",
            return_value=self.feature_branch,
        ), mock.patch.object(_mp, "_git", side_effect=self._patched_git()):
            ok, msg = _mp._stage1_5_premerge_state_guard(
                self.ticket, worktree_path=self.repo, force=False
            )

        self.assertFalse(ok, "빈 브랜치는 차단되어야 한다")
        self.assertIn("Empty branch detected", msg)

        # develop HEAD 변동 0
        self.assertEqual(
            _head_sha(self.repo, "develop"),
            pre_merge_sha,
            "빈 브랜치 차단 시 develop HEAD 가 변경되어서는 안 된다",
        )


# ─── S4: T-905 정상 경로 (push 전 reset --hard merge_commit^) ─────────────────


class TestScenario4UndoDoneResetPreservesUnrelated(_CycleTestBase):
    """S4 — undo_done push 전 reset 전략 (`_strategy_reset` 동등 동작).

    회귀 박제: undo_done.py:396 의 `git reset --hard <merge_commit>^` 가
    별건 commit 손실 0 인지 검증.

    시나리오:
      1. develop 에 별건 ahead commit (a1) 추가
      2. feature 브랜치 분기 + commit
      3. develop 으로 돌아와 non-ff 머지 → merge_commit (M1)
      4. undo_done reset 시뮬: `git reset --hard M1^`
      5. develop HEAD == M1^ == a1 (별건 commit 보존)
    """

    def test_undo_done_reset_preserves_unrelated_ahead_commit(self) -> None:
        # 1. develop 에 별건 ahead commit
        a1_sha = self._add_unrelated_commit_on_develop(
            filename="ahead1.py", content="a1 = 1\n"
        )

        # 2-3. feature 분기 + commit + non-ff 머지
        feature_sha = self._make_feature_with_change()
        merge_commit = self._non_ff_merge()
        # M1^ == a1 이어야 한다 (직전 develop HEAD)
        m1_parent1 = _head_sha(self.repo, f"{merge_commit}^1")
        self.assertEqual(
            m1_parent1, a1_sha, "M1^1 은 별건 ahead commit 이어야 한다"
        )

        # 4. undo_done reset 시뮬
        _git_check(self.repo, "reset", "--hard", f"{merge_commit}^")

        # 5. develop HEAD == a1 (별건 commit 보존, feature commit 제외)
        head_after = _head_sha(self.repo, "develop")
        self.assertEqual(
            head_after,
            a1_sha,
            "T-905 reset 후 develop HEAD 는 별건 ahead commit 이어야 한다",
        )

        # feature commit 은 develop log 에서 제외되어야 한다
        log = _log_shas(self.repo, n=20)
        self.assertNotIn(
            feature_sha,
            log,
            "T-905 reset 후 feature commit 은 develop log 에 없어야 한다",
        )
        # 별건 ahead commit 은 보존되어야 한다
        self.assertIn(
            a1_sha,
            log,
            "T-905 reset 후 별건 ahead commit 은 develop 에 보존되어야 한다",
        )


# ─── S5: T-906 정상 경로 (Review→Done DnD 후속 — 워크트리 commit + 재머지) ──


class TestScenario5RemergeAfterFreshCommit(_CycleTestBase):
    """S5 — Done 롤백 후 워크트리에 다시 변경분 commit + 재머지.

    회귀 0 회로: 사용자가 undo_done 후 워크트리에 작업물을 다시 commit 하면
    feature 브랜치의 commits ahead > 0 이 되어 Stage 1.5 가드 통과 + anchor
    검증 통과 → develop HEAD = 정상 merge commit.

    시나리오:
      1. feature 브랜치 빈 상태 (undo_done 직후 시뮬)
      2. 워크트리(임시 repo 위 feature 브랜치) 에 변경분 1개 commit
      3. 가드 통과 + non-ff 머지 + anchor 검증 통과
      4. develop HEAD = 정상 merge commit
    """

    def test_remerge_after_fresh_commit_succeeds(self) -> None:
        # 1. 빈 feature 브랜치 (undo_done 직후 시뮬)
        self._make_empty_feature()
        pre_merge_sha = _head_sha(self.repo, "develop")

        # 1-1. 빈 상태에서는 가드가 차단해야 한다 (회귀 가드 자체)
        with mock.patch(
            "flow.branch_strategy.get_feature_branch_for_ticket",
            return_value=self.feature_branch,
        ), mock.patch.object(_mp, "_git", side_effect=self._patched_git()):
            ok_empty, _ = _mp._stage1_5_premerge_state_guard(
                self.ticket, worktree_path=self.repo, force=False
            )
        self.assertFalse(
            ok_empty, "빈 feature 브랜치 상태에서는 가드가 차단해야 한다"
        )

        # 2. 워크트리에 변경분 1개 commit
        _git_check(self.repo, "checkout", self.feature_branch)
        feat_path = os.path.join(self.repo, "feat.py")
        with open(feat_path, "w") as f:
            f.write("feat = 'remerge-success'\n")
        _git_check(self.repo, "add", "feat.py")
        _git_check(self.repo, "commit", "-m", f"feat({self.ticket}): re-add change")
        feature_sha = _head_sha(self.repo)
        _git_check(self.repo, "checkout", "develop")

        # 3. 가드 통과
        with mock.patch(
            "flow.branch_strategy.get_feature_branch_for_ticket",
            return_value=self.feature_branch,
        ), mock.patch.object(_mp, "_git", side_effect=self._patched_git()):
            ok, msg = _mp._stage1_5_premerge_state_guard(
                self.ticket, worktree_path=self.repo, force=False
            )
        self.assertTrue(
            ok, f"변경분 commit 후에는 가드가 통과해야 한다 (msg={msg})"
        )

        # 3-1. non-ff 머지 + anchor 검증 통과
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
        self.assertTrue(anchor_ok, "재머지 anchor 검증은 통과해야 한다")

        # 4. develop HEAD 정합 + feature commit 보존
        self.assertEqual(_head_sha(self.repo, "develop"), merge_commit)
        log = _log_shas(self.repo, n=20)
        self.assertIn(feature_sha, log, "재머지 후 feature commit 이 보존되어야 한다")


# ─── S6: T-440 회귀 차단 + parent1_mismatch advisory ─────────────────────────


class TestScenario6T440RegressionBlocked(_CycleTestBase):
    """S6 — T-440 회귀 시나리오 차단 (Stage 1.5) + advisory 발동.

    회귀 박제 (T-440 사례, 2026-05-08):
      - undo_done 직후 빈 워크트리/브랜치 상태에서 develop 위에 별건 revert
        commit 이 추가됨
      - flow-merge 가 그 위에서 빈 브랜치를 머지 시도 → anchor 실패 →
        `_handle_anchor_failure` 가 reset --hard pre_merge_develop_sha (= 별건
        commit) 실행
      - W03 의 두 가지 가드가 동시에 작동해야 한다:
        (1) Stage 1.5: 빈 브랜치 자체를 차단 (1차 방어선)
        (2) `_handle_anchor_failure` 의 parent1_mismatch advisory: 만약
            우회 경로로 anchor 단계까지 도달한 경우, reset_target ≠
            merge_commit^1 일 때 사용자에게 별건 commit 손실 가능성을 경고
            (advisory only, reset 차단은 하지 않음 — 자동 강제 정책 금지 캐논)
    """

    def test_empty_branch_on_unrelated_develop_blocked_at_stage1_5(self) -> None:
        """1차 방어선: 빈 브랜치 + 별건 commit 추가된 develop 에서 가드 차단."""
        # T-440 시퀀스 재현
        self._add_unrelated_commit_on_develop(
            filename="revert.py", content="r = 1\n"
        )  # 별건 revert commit (6efc6ef 시뮬)
        self._make_empty_feature()  # 빈 브랜치 (undo_done 재생성 직후 시뮬)
        pre_state_log = _log_shas(self.repo, n=20)
        pre_state_head = _head_sha(self.repo, "develop")

        with mock.patch(
            "flow.branch_strategy.get_feature_branch_for_ticket",
            return_value=self.feature_branch,
        ), mock.patch.object(_mp, "_git", side_effect=self._patched_git()):
            ok, msg = _mp._stage1_5_premerge_state_guard(
                self.ticket, worktree_path=self.repo, force=False
            )

        self.assertFalse(ok, "T-440 회귀 시나리오는 Stage 1.5 에서 차단되어야 한다")
        self.assertIn("Empty branch detected", msg)

        # develop HEAD / log 변동 0 — 빈 머지 + reset 모두 발생하지 않아야 한다
        self.assertEqual(
            _head_sha(self.repo, "develop"),
            pre_state_head,
            "T-440 차단 시 develop HEAD 가 변경되어서는 안 된다 (별건 commit 보존)",
        )
        self.assertEqual(
            _log_shas(self.repo, n=20),
            pre_state_log,
            "T-440 차단 시 develop log 가 변경되어서는 안 된다",
        )

    def test_handle_anchor_failure_parent1_mismatch_advisory(self) -> None:
        """2차 방어선: anchor 실패 시 reset_target ≠ merge_commit^1 advisory.

        advisory only — reset 자체는 차단하지 않으며 사용자에게 의심 케이스를
        명시 경고한다. 자동 강제 정책 도입 금지 캐논 준수.
        """
        # 정상 non-ff 머지 commit 을 먼저 만든다 (anchor 비교 대상 확보)
        self._make_feature_with_change()
        pre_merge_sha = _head_sha(self.repo, "develop")
        merge_commit = self._non_ff_merge()
        # merge_commit^1 == pre_merge_sha (정상 케이스)
        self.assertEqual(_head_sha(self.repo, f"{merge_commit}^1"), pre_merge_sha)

        # T-440 시뮬: pre_merge_develop_sha 가 별건 commit 으로 캡처된 케이스
        # 즉 reset_target = bogus_unrelated_sha != merge_commit^1
        # 이때 _handle_anchor_failure 는 advisory 를 출력해야 한다
        # (reset 자체는 진행 — advisory only)
        bogus_sha = "deadbeef" * 5  # 40자 가짜 SHA (실 reset 시도 시 실패)

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
        # advisory 마커 확인
        self.assertIn(
            "[ANCHOR][T-441]",
            all_errors,
            "parent1_mismatch advisory 마커가 출력되어야 한다",
        )
        self.assertIn(
            "의심 케이스",
            all_errors,
            "advisory 가 의심 케이스를 명시해야 한다",
        )

    def test_handle_anchor_failure_normal_case_no_advisory(self) -> None:
        """정상 케이스 (reset_target == merge_commit^1) 에서는 advisory 미출력 (회귀 0)."""
        self._make_feature_with_change()
        pre_merge_sha = _head_sha(self.repo, "develop")
        merge_commit = self._non_ff_merge()

        error_messages: list[str] = []

        def fake_error(msg: str) -> None:
            error_messages.append(msg)

        # ^2 rev-parse 결과를 변조하여 anchor 실패 강제하고 정상 reset_target 으로 호출
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
        # parent1 일치 정상 케이스에서는 [T-441] 의심 케이스 마커가 없어야 한다
        self.assertNotIn(
            "의심 케이스",
            all_errors,
            "정상 reset_target == merge_commit^1 케이스에서는 advisory 가 출력되어서는 안 된다",
        )


if __name__ == "__main__":
    unittest.main()
