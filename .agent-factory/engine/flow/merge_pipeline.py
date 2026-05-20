#!/usr/bin/env -S python3 -u
"""merge_pipeline.py - 워크트리 병합 파이프라인 자동화 스크립트.

worktree 환경에서 feature 브랜치를 develop에 병합하고 정리하는
5단계 파이프라인을 단일 커맨드로 실행한다.

사용법:
  flow-merge <ticket_number> [--dry-run] [--force]

파이프라인 단계:
  1. 미커밋 변경사항 감지 및 자동 커밋
  2. feature 브랜치를 develop에 --no-ff 병합
  2.5. merge anchor 검증 (WORKFLOW_WORKTREE=true 시에만 활성)
  3. worktree unlock + remove (+ feature 브랜치 삭제)
  4. kanban done 처리 (worktree merge hook 중복 방지)
  5. (feature 브랜치 삭제는 3단계에서 처리됨)

옵션:
  --dry-run   각 단계의 예상 동작만 출력하고 실제 수행하지 않음
  --force     merge 승인 검사를 우회 (직접 호출 시)

종료 코드:
  0  성공
  1  병합 충돌 또는 실패
  2  인자 오류 또는 승인 미비
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

# ─── sys.path guaranteed ───────────────────────────────────────────────────────────────

# Symlink/relative path analysis correction (worktree environment response)
__file__ = os.path.realpath(__file__)

_engine_dir: str = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
)
if _engine_dir not in sys.path:
    sys.path.insert(0, _engine_dir)

from common import resolve_project_root

# ─── Constant ───────────────────────────────────────────────────────────────────────

_MERGE_APPROVED_ENV: str = "WORKFLOW_MERGE_APPROVED"
_ANCHOR_FAILURE_LOG: str = os.path.join(
    ".agent-factory", "logs", "merge-anchor-failures.log"
)

# KST (UTC+9)
_KST = timezone(timedelta(hours=9))


# ─── Internal Utilities ────────────────────────────────────────────────────────────────


def _git(
    *args: str, repo_path: str | None = None
) -> subprocess.CompletedProcess[str]:
    """git 명령을 실행하고 결과를 반환한다.

    Args:
        *args: git 서브커맨드 및 인자.
        repo_path: git 저장소 경로. None이면 resolve_project_root() 사용.

    Returns:
        CompletedProcess 인스턴스.
    """
    cwd = repo_path or resolve_project_root()
    cmd = ["git", "-C", cwd] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True, timeout=30)


def _info(msg: str) -> None:
    """Prints information messages to stderr."""
    print(f"[INFO] flow-merge: {msg}", file=sys.stderr, flush=True)


def _error(msg: str) -> None:
    """Prints error messages to stderr."""
    print(f"[ERROR] flow-merge: {msg}", file=sys.stderr, flush=True)


def _step(num: int, desc: str) -> None:
    """Prints pipeline stage headers."""
    print(f"\n── Stage {num}: {desc} ──", flush=True)


# ─── Pipeline stages ──────────────────────────────────────────────────────────────


def _normalize_ticket(ticket_number: str) -> str:
    """티켓 번호를 T-NNN 형식으로 정규화한다.

    Args:
        ticket_number: 원본 티켓 번호. 숫자만 있으면 T- 접두사 추가.

    Returns:
        T-NNN 형식 티켓 번호.
    """
    if not ticket_number.startswith("T-"):
        ticket_number = f"T-{ticket_number}"
    return ticket_number


def _check_merge_approval(force: bool) -> bool:
    """merge 승인 여부를 검사한다.

    직접 flow-merge 호출 시 WORKFLOW_MERGE_APPROVED 환경변수가
    설정되어 있거나 --force 옵션이 있어야 실행을 허용한다.

    Args:
        force: --force 옵션 사용 여부.

    Returns:
        승인되었으면 True, 미승인이면 False.
    """
    if force:
        return True
    if os.environ.get(_MERGE_APPROVED_ENV) == "1":
        return True
    return False


def _count_commits_ahead(branch: str, base: str = "develop") -> int | None:
    """`git rev-list base..branch --count` 결과를 반환한다.

    Args:
        branch: 검사 대상 feature 브랜치명.
        base: 기준 브랜치명 (기본 develop).

    Returns:
        commits ahead 개수. 명령 실패(브랜치 부재 등) 시 None.
    """
    result = _git("rev-list", f"{base}..{branch}", "--count")
    if result.returncode != 0:
        return None
    raw = result.stdout.strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _branch_exists(branch: str) -> bool:
    """로컬에 feature 브랜치가 존재하는지 검사한다.

    Args:
        branch: 검사할 브랜치명.

    Returns:
        존재하면 True, 없으면 False.
    """
    if not branch:
        return False
    result = _git("rev-parse", "--verify", "--quiet", f"refs/heads/{branch}")
    return result.returncode == 0


def _stage1_5_premerge_state_guard(
    ticket_number: str,
    worktree_path: str | None,
    force: bool,
) -> tuple[bool, str]:
    """Stage 1.5: 재머지 진입 직전 워크트리/feature 브랜치 상태 가드.

    회귀 차단: Done 롤백(undo_done) 후 워크트리·feature 브랜치가
    빈 상태(변경분 없이 재생성됨)이거나 부재인 채로 재머지가 진행되어
    별건 commit 위에서 anchor 실패 → `reset --hard pre_merge_develop_sha` 가
    별건 변경분을 함께 reset 하는 회귀가 발생했다.

    본 가드는 Stage 2(`merge_to_develop`) 진입 전에 다음을 검증한다:

    1. feature 브랜치 부재 → 항상 차단(force 무관). undo_done 직후 재생성
       단계 누락이거나 워크트리 자체가 없는 케이스.
    2. feature 브랜치 존재 + commits ahead == 0(빈 브랜치) →
       force=False: 차단 + 명확한 에러
       force=True: 차단 + reflog fallback 안내 (자동 트리거 금지)
    3. 정상(commits ahead > 0) → 통과

    회귀 0 보장:

        commits ahead > 0 이므로 통과.

        재머지 단계에서만 작동.
      - 자동 회귀·자동 reflog 적용 금지(feedback_no_speculative_guards
        2026-05-08 캐논). 사용자 명시 동의 메시지만 노출.

    Args:
        ticket_number: 티켓 번호 (T-NNN).
        worktree_path: get_worktree_path 반환값. 부재 시 None.
        force: --force 옵션 사용 여부.

    Returns:
        (ok, message) 튜플. ok=True 면 통과, False 면 호출자가 즉시 종료.
        message 는 stderr 로그 용도(통과 시 빈 문자열).
    """
    _step(1, "Jammer state guard (Stage 1.5)")

    # branch_strategy has a high call cost, so it is lazy imported.
    try:
        from flow.branch_strategy import get_feature_branch_for_ticket
    except Exception as exc:  # pragma: no cover - import path abnormal
        _error(f"[GUARD] branch_strategy import failed: {exc}")
        return False, "branch_strategy import failed"

    branch_name = get_feature_branch_for_ticket(ticket_number)

    # ── 1. Absence of feature branch ──
    if not branch_name or not _branch_exists(branch_name):
        wt_status = "absence" if not worktree_path else f"exists({worktree_path})"
        msg = (
            f"Absence of feature branch: ticket={ticket_number}"
            f"branch={branch_name or '<unresolved>'} worktree={wt_status}"
        )
        _error(f"[GUARD] {msg}")
        if force:
            print(
                "force mode allows destructive behavior and therefore requires explicit user consent."
                "You need it. \n"
                "Recovery Options (Manual): \n"
                "1) Regenerate work tree/branch with `flow-undo-done <T-NNN> --force` \n"
                "2) Check the original merge commit SHA in the develop reflog: \n"
                "       git reflog develop --grep-reflog='merge.*' | grep "
                f"feat/{ticket_number}\n"
                "3) Cherry-pick the SHA containing the changes to a new branch and remerge it.",
                file=sys.stderr,
                flush=True,
            )
        else:
            print(
                "An empty merge was blocked because the feature branch could not be found. \n"
                "Recreate it with `flow-undo-done <T-NNN> --force` and retry.",
                file=sys.stderr,
                flush=True,
            )
        return False, msg

    # ── 2. Existence of feature branch + empty branch (commits ahead == 0) ──
    ahead = _count_commits_ahead(branch_name, base="develop")
    if ahead is None:
        # rev-list failure — abnormal, such as absence of develop. block.
        msg = (
            f"Failed to calculate commits ahead: branch={branch_name} base=develop"
            "(develop branch missing or rev-list failed)"
        )
        _error(f"[GUARD] {msg}")
        return False, msg

    if ahead == 0:
        msg = (
            f"Empty branch detected: feature '{branch_name}' has no commits "
            "ahead of develop. Refusing empty merge."
        )
        _error(f"[GUARD] {msg}")
        if force:
            print(
                "Even in force mode, empty branches are not automatically merged."
                "(User express consent Canon). \n"
                "Recovery Options (Manual): \n"
                "1) Check the original merge commit SHA in the develop reflog: \n"
                "       git reflog develop --grep-reflog='merge.*' | grep "
                f"feat/{ticket_number}\n"
                "2) Cherry-pick the SHA containing the changes to a new branch and remerge \n"
                "3) Or, after regenerating the work tree with `flow-undo-done <T-NNN> --force`, \n"
                "Commit the work again and remerge it",
                file=sys.stderr,
                flush=True,
            )
        else:
            print(
                "Merging empty branches is blocked due to the risk of reproducing regressions. \n"
                "Commit the changes to the work tree and retry.",
                file=sys.stderr,
                flush=True,
            )
        return False, msg

    # ── 3. Normal pass ──
    print(
        f"Feature branch top: {branch_name} ({ahead} commit ahead of develop)",
        flush=True,
    )
    return True, ""


def _stage1_auto_commit(
    ticket_number: str, worktree_path: str, dry_run: bool
) -> bool:
    """Stage 1: worktree 내 미커밋 변경사항을 감지하고 자동 커밋한다.

    Args:
        ticket_number: 티켓 번호 (T-NNN).
        worktree_path: worktree 절대 경로.
        dry_run: True이면 변경 파일 목록만 출력.

    Returns:
        성공 시 True, 실패 시 False.
    """
    _step(1, "Detect uncommitted changes and automatically commit them")

    # Detect changes with git status --porcelain
    result = _git("status", "--porcelain", repo_path=worktree_path)
    if result.returncode != 0:
        _error(f"git status failed: {result.stderr.strip()}")
        return False

    changed_files = [
        line.strip() for line in result.stdout.splitlines() if line.strip()
    ]

    if not changed_files:
        print("No changes (no commit required)", flush=True)
        return True

    print(f"Detect {len(changed_files)} uncommitted files:", flush=True)
    for f in changed_files:
        print(f"    {f}", flush=True)

    if dry_run:
        print("[DRY-RUN] Skip autocommit", flush=True)
        return True

    # git add -A + commit
    add_result = _git("add", "-A", repo_path=worktree_path)
    if add_result.returncode != 0:
        _error(f"git add failed: {add_result.stderr.strip()}")
        return False

    commit_msg = f"chore: auto-commit before merge ({ticket_number})"
    commit_result = _git(
        "commit", "-m", commit_msg, repo_path=worktree_path
    )
    if commit_result.returncode != 0:
        _error(f"git commit failed: {commit_result.stderr.strip()}")
        return False

    print(f"Autocommit completed: {commit_msg}", flush=True)
    return True


def _stage2_merge_to_develop(
    ticket_number: str, dry_run: bool
) -> tuple[bool, str, str]:
    """Stage 2: feature 브랜치를 develop에 --no-ff 병합한다.

    worktree_manager.merge_to_develop()를 재사용한다.
    병합 충돌 시 abort 후 충돌 파일 목록을 출력한다.

    Args:
        ticket_number: 티켓 번호 (T-NNN).
        dry_run: True이면 예상 동작만 출력.

    Returns:
        (success, merge_commit_sha, feature_branch) 튜플.
        성공 시 (True, sha, branch), 실패 시 (False, "", "").
    """
    _step(2, "Feature branch -> develop merge")

    from flow.branch_strategy import get_feature_branch_for_ticket
    from flow.worktree_manager import merge_to_develop

    branch_name = get_feature_branch_for_ticket(ticket_number)
    if not branch_name:
        _error(f"The feature branch linked to {ticket_number} could not be found")
        return False, "", ""

    print(f"Target branch: {branch_name}", flush=True)

    if dry_run:
        print(
            f"  [DRY-RUN] git merge --no-ff {branch_name} into develop",
            flush=True,
        )
        return True, "", branch_name

    merge_result = merge_to_develop(ticket_number)
    if not merge_result.success:
        if merge_result.conflicts:
            _error("Merge conflict occurred (merge --abort completed)")
            print("Conflicting files:", flush=True)
            for cf in merge_result.conflicts:
                print(f"    - {cf}", flush=True)
            print(
                "Please resolve the conflict in the worktree and try again.",
                flush=True,
            )
        else:
            _error(f"Merge failed: {merge_result.error_message}")
        return False, "", ""

    print(
        f"Merge completed: {merge_result.merged_branch} -> develop"
        f"({merge_result.merge_commit[:8]})",
        flush=True,
    )
    return True, merge_result.merge_commit, merge_result.merged_branch


def _handle_anchor_failure(
    merge_commit: str,
    feature_branch: str,
    reason: str,
    pre_merge_develop_sha: str = "",
) -> None:
    """merge anchor 검증 실패 시 롤백 및 로그 기록을 수행한다.

    현재 HEAD가 merge_commit과 일치하면 명시적 SHA 리셋(`pre_merge_develop_sha`)
    또는 fallback 으로 `HEAD^` 리셋을 수행하고,
    .agent-factory/logs/merge-anchor-failures.log에 JSONL 형식으로 기록한다.

    Args:
        merge_commit: 병합 커밋 SHA.
        feature_branch: feature 브랜치명.
        reason: 실패 이유.
        pre_merge_develop_sha: Stage 2 진입 직전 캡처한 develop HEAD SHA.
            비어있지 않으면 `git reset --hard <pre_merge_develop_sha>` 로
            명시적 SHA 리셋을 수행한다 (T-403 회귀 방지: develop 의 사전
            ahead commit 이 자동 보존됨).
            빈 문자열이면 캡처 실패 fallback 으로 기존 `HEAD^` 상대 경로
            리셋을 수행하고 경고 로그를 출력한다.
    """
    project_root = resolve_project_root()

    # Forensics 1: Record develop HEAD before running reset
    head_before_result = _git("rev-parse", "HEAD")
    head_before = (
        head_before_result.stdout.strip()
        if head_before_result.returncode == 0
        else ""
    )

    # Rollback SHA decision: pre_merge_develop_sha first, HEAD^ fallback if not reserved
    if pre_merge_develop_sha:
        reset_target = pre_merge_develop_sha
    else:
        _error(
            "[ANCHOR] Do not have pre_merge_develop_sha — Do not have accurate SHA;"
            "Perform relative reset (HEAD^ fallback)"
        )
        reset_target = "HEAD^"

    # Forensics 1.5: Check if reset_target matches the first parent of merge commit.
    # A separate commit (`6efc6ef` revert, etc.) had been added, and pre_merge_develop_sha had been added.
    # 그 별건 commit 으로 캡처되어 `reset --hard <commit separately>` 이 실행되면서
    # Reset to a different location from the develop state just before merging → Possibility of loss of changes.
    # If parent1 == reset_target, normal (reverts to the state just before merging),
    # Otherwise, it is a suspicious case captured above the commit, so the warning log is strengthened.
    # However, this test only performs advisory and does not block the reset itself.
    # (Canon prohibits introduction of automatic enforcement policy).
    parent1_mismatch = False
    if reset_target and reset_target != "HEAD^":
        parent1_result = _git("rev-parse", f"{merge_commit}^1")
        if parent1_result.returncode == 0:
            parent1_sha = parent1_result.stdout.strip()
            if parent1_sha and parent1_sha != reset_target:
                parent1_mismatch = True
                _error(
                    f"[ANCHOR][T-441] Suspicious case: reset_target"
                    f"({reset_target[:8]}) != merge_commit^1 "
                    f"({parent1_sha[:8]}). "
                    "Separately, pre_merge_develop_sha was captured above the commit."
                    "possibility. After reset, you need to check the develop changes."
                )

    # Rollback after checking HEAD matches merge_commit
    rollback_executed = False
    rollback_succeeded = False
    if head_before_result.returncode == 0 and head_before == merge_commit:
        reset_result = _git("reset", "--hard", reset_target)
        rollback_executed = True
        if reset_result.returncode == 0:
            rollback_succeeded = True
            _error(
                f"Merge rollback completed due to anchor verification failure"
                f"(reason: {reason}, reset_target: {reset_target})"
            )
            if parent1_mismatch:
                _error(
                    "[ANCHOR][T-441] Additional commits may be lost after rollback —"
                    "Check the develop reflog and work tree changes directly."
                )
        else:
            _error(
                f"anchor verification failure + rollback failure"
                f"(reset_target: {reset_target}): "
                f"{reset_result.stderr.strip()}"
            )
    else:
        _error(
            f"anchor verification failed (HEAD != merge_commit, rollback skipped): {reason}"
        )

    # Forensics 2: Record develop HEAD after executing reset
    head_after_result = _git("rev-parse", "HEAD")
    head_after = (
        head_after_result.stdout.strip()
        if head_after_result.returncode == 0
        else ""
    )

    # JSONL log history — pre_merge_develop_sha / reset_target / head_before /
    log_path = os.path.join(project_root, _ANCHOR_FAILURE_LOG)
    try:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        ts = datetime.now(_KST).strftime("%Y-%m-%dT%H:%M:%S")
        record = {
            "timestamp": ts,
            "merge_commit": merge_commit,
            "feature_branch": feature_branch,
            "reason": reason,
            "pre_merge_develop_sha": pre_merge_develop_sha,
            "reset_target": reset_target,
            "head_before_reset": head_before,
            "head_after_reset": head_after,
            "rollback_executed": rollback_executed,
            "rollback_succeeded": rollback_succeeded,
            "parent1_mismatch": parent1_mismatch,
        }
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        _error(f"anchor failure Logging failure: {e}")


def _stage2_5_verify_merge_anchor(
    merge_commit: str,
    feature_branch: str,
    dry_run: bool,
    pre_merge_develop_sha: str = "",
) -> bool:
    """Stage 2.5: merge anchor 검증을 수행한다.

    WORKFLOW_WORKTREE=false(기본값)이면 즉시 True를 반환하여 스킵한다.
    활성화 시 두 가지 검증을 수행한다:
      1. 병합 커밋의 두 번째 부모(^2) SHA == feature_branch HEAD SHA
      2. git diff {merge_commit}^2 {merge_commit} 출력이 비어있어야 함

    Args:
        merge_commit: Stage 2에서 생성된 병합 커밋 SHA.
        feature_branch: 병합된 feature 브랜치명.
        dry_run: True이면 예상 동작만 출력.
        pre_merge_develop_sha: Stage 2 진입 직전 캡처한 develop HEAD SHA.
            T-410: merge_commit == pre_merge_develop_sha 이면 git merge
            --no-ff 가 새 commit 을 만들지 않은 already-up-to-date 케이스이므로
            anchor 검증 자체를 skip 한다 (^2 호출 회피).
            빈 문자열이면 미캡처 상태로 간주하고 기존 분기를 따른다.

    Returns:
        검증 성공(또는 스킵) 시 True, 실패(롤백 완료) 시 False.
    """
    _step(2, "Merge anchor verification (Stage 2.5)")

    from flow.worktree_manager import is_worktree_enabled

    if not is_worktree_enabled():
        print(
            "[ANCHOR] WORKFLOW_WORKTREE=false — Skip anchor verification",
            flush=True,
        )
        return True

    if dry_run:
        print(
            f"[ANCHOR] [DRY-RUN] merge anchor verification:"
            f"{merge_commit[:8]} / {feature_branch}",
            flush=True,
        )
        return True

    if not merge_commit:
        _error("anchor verification: unable to verify because merge_commit is empty")
        return True  # Non-blocking: Pass if verification is not possible

    # `git merge --no-ff` creates a new commit when the feature is the ancestor of develop
    # Returns the existing develop HEAD as is without creating it. In this case merge_commit is
    # It is the same as pre_merge_develop_sha, and anchor verification (^2 comparison) is meaningless.
    # By avoiding the `^2` call itself, the possibility of false-fail due to fall-through is blocked.
    if pre_merge_develop_sha and merge_commit == pre_merge_develop_sha:
        print(
            f"[ANCHOR] already-up-to-date — Skip anchor verification"
            f"(merge_commit {merge_commit[:8]} == "
            f"pre_merge_develop_sha {pre_merge_develop_sha[:8]})",
            flush=True,
        )
        return True

    # Verification 1: merge_commit^2 == feature_branch HEAD
    parent2_result = _git("rev-parse", f"{merge_commit}^2")
    if parent2_result.returncode != 0:
        # fast-forward or already-up-to-date case (1 parent).
        # There is no additional merge commit in develop, so anchor verification is meaningless → skip.
        # Data loss regression occurs even before the develop commit.
        # Structure the reason for the branch (distinguish between capture failure and SHA mismatch).
        if not pre_merge_develop_sha:
            sha_compare = "pre_merge_develop_sha not captured"
        elif merge_commit == pre_merge_develop_sha:
            # This path should have already been processed in the explicit branch above, but is marked defensively.
            sha_compare = (
                f"== pre_merge_develop_sha {pre_merge_develop_sha[:8]} "
                f"(up-to-date)"
            )
        else:
            sha_compare = (
                f"!= pre_merge_develop_sha {pre_merge_develop_sha[:8]} "
                f"(ff merge estimation)"
            )
        print(
            f"[ANCHOR] fast-forward / up-to-date — skip anchor verification"
            f"(merge_commit {merge_commit[:8]} 1 parent, {sha_compare})",
            flush=True,
        )
        return True

    fb_head_result = _git("rev-parse", feature_branch)
    if fb_head_result.returncode != 0:
        # Skip verification if feature branch has already been deleted (non-blocking)
        _info(
            f"[ANCHOR] Skip anchor verification: feature_branch {feature_branch}"
            f"Not found (already deleted)"
        )
        return True

    parent2_sha = parent2_result.stdout.strip()
    fb_head_sha = fb_head_result.stdout.strip()

    if parent2_sha != fb_head_sha:
        reason = (
            f"^2 SHA ({parent2_sha[:8]}) != feature HEAD ({fb_head_sha[:8]})"
        )
        _error(f"[ANCHOR] anchor validation failed: {reason}")
        _handle_anchor_failure(
            merge_commit, feature_branch, reason, pre_merge_develop_sha
        )
        return False

    # Verification 2: git diff {merge_commit}^2 {merge_commit} must be empty
    diff_result = _git(
        "diff", f"{merge_commit}^2", merge_commit
    )
    if diff_result.returncode != 0:
        _error(
            f"[ANCHOR] anchor validation failed: git diff command failed —"
            f"{diff_result.stderr.strip()}"
        )
        _handle_anchor_failure(
            merge_commit,
            feature_branch,
            "git diff command failed",
            pre_merge_develop_sha,
        )
        return False

    if diff_result.stdout.strip():
        reason = (
            f"diff {merge_commit[:8]}^2..{merge_commit[:8]} output is not empty"
        )
        _error(f"[ANCHOR] anchor validation failed: {reason}")
        _handle_anchor_failure(
            merge_commit, feature_branch, reason, pre_merge_develop_sha
        )
        return False

    print(
        f"[ANCHOR] anchor validation passed: {merge_commit[:8]} / {feature_branch}",
        flush=True,
    )
    return True


def _stage3_remove_worktree(
    ticket_number: str, dry_run: bool
) -> bool:
    """Stage 3: worktree unlock + remove (+ feature 브랜치 삭제).

    worktree_manager.remove_worktree()를 재사용한다.
    merge_to_develop()가 이미 remove_worktree를 호출하므로,
    잔여 worktree가 있는 경우에만 정리한다 (멱등).

    Args:
        ticket_number: 티켓 번호 (T-NNN).
        dry_run: True이면 예상 동작만 출력.

    Returns:
        성공 시 True, 실패 시 False.
    """
    _step(3, "Remove worktree + delete feature branch")

    from flow.worktree_manager import get_worktree_path, remove_worktree

    wt_path = get_worktree_path(ticket_number)
    if wt_path:
        print(f"worktree path: {wt_path}", flush=True)
    else:
        print(
            "worktree already removed (cleanup completed in Stage 2)",
            flush=True,
        )
        return True

    if dry_run:
        print(
            f"  [DRY-RUN] worktree unlock + remove: {wt_path}",
            flush=True,
        )
        print("[DRY-RUN] Delete feature branch", flush=True)
        return True

    success = remove_worktree(
        ticket_number, delete_branch=True
    )
    if not success:
        _error("Worktree removal failed")
        return False

    print("worktree removal complete", flush=True)
    return True


def _stage4_kanban_done(
    ticket_number: str, dry_run: bool
) -> bool:
    """Stage 4: kanban done 처리.

    kanban_cli.cmd_done()을 호출한다. cmd_done() 내부의 worktree
    merge hook은 feature 브랜치가 이미 삭제된 상태이므로
    get_feature_branch_for_ticket()이 None을 반환하여 자동으로
    중복 merge를 건너뛴다.

    Args:
        ticket_number: 티켓 번호 (T-NNN).
        dry_run: True이면 예상 동작만 출력.

    Returns:
        성공 시 True, 실패 시 False.
    """
    _step(4, "kanban done processing")

    if dry_run:
        print(
            f"  [DRY-RUN] kanban done {ticket_number}",
            flush=True,
        )
        print(
            "[DRY-RUN] Worktree merge hook is skipped due to non-existence of feature branch",
            flush=True,
        )
        return True

    try:
        from flow.kanban_cli import cmd_done

        cmd_done(ticket_number)
        print(f"kanban done done: {ticket_number}", flush=True)
        return True
    except SystemExit as e:
        if e.code and e.code != 0:
            _error(f"kanban done failed (exit code: {e.code})")
            return False
        return True
    except Exception as e:
        _error(f"kanban done failed: {e}")
        return False


# ─── Main pipeline ──────────────────────────────────────────────────────────────


def run_pipeline(
    ticket_number: str, dry_run: bool = False, force: bool = False
) -> int:
    """5단계 병합 파이프라인을 순차 실행한다.

    Args:
        ticket_number: 티켓 번호 (T-NNN 형식 또는 숫자).
        dry_run: True이면 각 단계의 예상 동작만 출력.
        force: True이면 merge 승인 검사를 우회.

    Returns:
        종료 코드. 0=성공, 1=병합실패, 2=승인미비.
    """
    ticket_number = _normalize_ticket(ticket_number)

    print(f"=== flow-merge: {ticket_number} ===", flush=True)
    if dry_run:
        print("[DRY-RUN mode] Does not actually run \n", flush=True)

    # ── Approval inspection ──
    if not _check_merge_approval(force):
        _error(
            "Merge approval is required."
            "Use the /wf -d command or add the --force option."
        )
        return 2

    # ── Worktree path navigation ──
    from flow.worktree_manager import get_worktree_path

    worktree_path = get_worktree_path(ticket_number)

    # ── Stage 1: Automatically commit uncommitted changes ──
    if worktree_path:
        if not _stage1_auto_commit(ticket_number, worktree_path, dry_run):
            return 1
    else:
        _step(1, "Detect uncommitted changes and automatically commit them")
        print("No worktree (Skip Stage 1)", flush=True)

    # Since dry-run does not perform actual merge, the guard result is marked as advisory and passes.
    guard_ok, _guard_msg = _stage1_5_premerge_state_guard(
        ticket_number, worktree_path, force
    )
    if not guard_ok:
        if dry_run:
            print(
                "[DRY-RUN] Guard failure — would have been blocked in real merge (continued)",
                flush=True,
            )
        else:
            return 1

    # already-up-to-date / ff Case specification Used to specify branch + rollback SHA.
    # Fallback to an empty string if the develop branch does not exist or rev-parse fails —
    # Both _stage2_5_verify_merge_anchor and _handle_anchor_failure
    # Maintain existing behavior with backward-compat default("").
    pre_merge_develop_sha_result = _git("rev-parse", "develop")
    if pre_merge_develop_sha_result.returncode == 0:
        pre_merge_develop_sha = pre_merge_develop_sha_result.stdout.strip()
    else:
        pre_merge_develop_sha = ""
        _info(
            "[ANCHOR] pre_merge_develop_sha capture failed — develop branch not present or"
            f"rev-parse failed: {pre_merge_develop_sha_result.stderr.strip()}"
        )

    # ── Stage 2: feature -> develop merge ──
    stage2_success, merge_commit, feature_branch = _stage2_merge_to_develop(
        ticket_number, dry_run
    )
    if not stage2_success:
        return 1

    # ── Stage 2.5: Merge anchor verification ──
    if not _stage2_5_verify_merge_anchor(
        merge_commit, feature_branch, dry_run, pre_merge_develop_sha
    ):
        return 1

    # ── Stage 3: Worktree removal + branch deletion ──
    if not _stage3_remove_worktree(ticket_number, dry_run):
        # If worktree removal fails, just output a warning and continue.
        _info("Removal of the worktree failed, but the merge was completed, so continue.")

    # ── Stage 4: kanban done ──
    if not _stage4_kanban_done(ticket_number, dry_run):
        # If kanban done fails, only a warning is output.
        _info("kanban done failed, but merge was completed")

    # ── Stage 5: Delete feature branch (processing completed in Stage 3) ──
    _step(5, "Delete feature branch")
    print("Processing completed in Stage 3 (delete_branch=True)", flush=True)

    print(f"\n === flow-merge completed: {ticket_number} ===", flush=True)
    return 0


# ─── CLI ──────────────────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    """CLI 인자 파서를 구성한다.

    Returns:
        구성된 ArgumentParser 인스턴스.
    """
    parser = argparse.ArgumentParser(
        prog="flow-merge",
        description="Worktree Merge Pipeline Automation",
    )
    parser.add_argument(
        "ticket_number",
        help="Ticket number (T-NNN or numeric)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Prints only expected behavior and does not actually perform it",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Bypass merge approval check (when calling directly)",
    )
    return parser


def main() -> None:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()

    exit_code = run_pipeline(
        ticket_number=args.ticket_number,
        dry_run=args.dry_run,
        force=args.force,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
