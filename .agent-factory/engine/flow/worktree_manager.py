"""worktree_manager.py - Git worktree 격리 실행 관리 모듈.

워크플로우별 독립 git worktree를 생성/삭제하고, feature 브랜치를
develop에 병합하는 기능을 제공한다. branch_strategy.py에 의존한다.

데이터 클래스:
    WorktreeInfo: worktree 메타데이터
    MergeResult: 병합 결과

공개 API:
    is_worktree_enabled: worktree 기능 활성화 여부 판단
    create_worktree: 티켓용 worktree 생성
    has_uncommitted_changes: worktree 경로의 미커밋 변경 여부 검사
    count_feature_branch_commits: feature 브랜치의 커밋 수 반환 (워커 commit 누락 탐지)
    remove_worktree: worktree 제거 (멱등)
    merge_to_develop: feature 브랜치를 develop에 병합
    list_worktrees: 활성 worktree 목록 조회
    get_worktree_path: 티켓에 연결된 worktree 경로 조회
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime

# ─── sys.path guaranteed ───────────────────────────────────────────────────────────────

_engine_dir: str = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
)
_agent_factory_dir: str = os.path.dirname(_engine_dir)
if _agent_factory_dir not in sys.path:
    sys.path.insert(0, _agent_factory_dir)
if _engine_dir not in sys.path:
    sys.path.insert(0, _engine_dir)

from engine.adapters.git.cli import run_git
from engine.core.worktrees.paths import (
    merge_lock_path,
    normalize_ticket_number,
    worktree_dir_name,
    worktree_path_for_branch,
    worktrees_base_dir,
)

from common import acquire_lock, read_env, release_lock, resolve_project_root
from flow.branch_strategy import (
    create_feature_branch,
    delete_feature_branch,
    ensure_develop_branch,
    get_feature_branch_for_ticket,
)

# ─── Data class ───────────────────────────────────────────────────────────────


@dataclass
class WorktreeInfo:
    """worktree 메타데이터를 담는 데이터 클래스.

    Attributes:
        path: worktree 절대 경로.
        branch_name: 연결된 feature 브랜치명 (예: feat/T-001-제목).
        ticket_number: 티켓 번호 (예: T-001).
        created_at: 생성 시각 (ISO 8601 형식).
        base_branch: 기준 브랜치. 기본값 'develop'.
    """

    path: str
    branch_name: str
    ticket_number: str
    created_at: str
    base_branch: str = "develop"


@dataclass
class MergeResult:
    """병합 결과를 담는 데이터 클래스.

    Attributes:
        success: 병합 성공 여부.
        conflicts: 충돌 파일 목록 (실패 시).
        merged_branch: 병합된 feature 브랜치명 (성공 시).
        merge_commit: 병합 커밋 SHA (성공 시).
        error_message: 에러 메시지 (실패 시).
    """

    success: bool
    conflicts: list[str] = field(default_factory=list)
    merged_branch: str = ""
    merge_commit: str = ""
    error_message: str = ""


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
    return run_git(*args, repo_path=cwd, timeout=30)


def _get_project_root(repo_path: str | None = None) -> str:
    """Returns the absolute path to the project root."""
    return repo_path or resolve_project_root()


def _worktrees_base_dir(repo_path: str | None = None) -> str:
    """worktree가 저장되는 상위 디렉터리 경로를 반환한다.

    Returns:
        프로젝트 루트 아래 .worktrees/ 절대 경로.
    """
    return str(worktrees_base_dir(_get_project_root(repo_path)))


def _merge_lock_path(repo_path: str | None = None) -> str:
    """병합 잠금 디렉터리 경로를 반환한다.

    Returns:
        .git/worktree-merge.lockdir 절대 경로.
    """
    return str(merge_lock_path(_get_project_root(repo_path)))


def _worktree_dir_name(branch_name: str) -> str:
    """브랜치명을 worktree 디렉터리명으로 변환한다.

    feat/T-NNN-제목 -> feat-T-NNN-제목 (슬래시를 하이픈으로).

    Args:
        branch_name: feature 브랜치명.

    Returns:
        디렉터리명 (슬래시 없음).
    """
    return worktree_dir_name(branch_name)


def _get_current_branch(repo_path: str | None = None) -> str:
    """현재 체크아웃된 브랜치명을 반환한다.

    Args:
        repo_path: git 저장소 경로.

    Returns:
        현재 브랜치명. detached HEAD이면 빈 문자열.
    """
    result = _git("rev-parse", "--abbrev-ref", "HEAD", repo_path=repo_path)
    if result.returncode != 0:
        return ""
    branch = result.stdout.strip()
    return "" if branch == "HEAD" else branch


def _warn(msg: str) -> None:
    """Prints a warning message to stderr."""
    print(f"[WARN] worktree_manager: {msg}", file=sys.stderr)


def _info(msg: str) -> None:
    """Prints information messages to stderr."""
    print(f"[INFO] worktree_manager: {msg}", file=sys.stderr)


def _append_worktree_io(
    op: str,
    duration_ms: int,
    outcome: str,
    error_reason: str | None = None,
) -> None:
    """worktree.io 이벤트를 metrics.jsonl에 기록한다.

    work_dir 는 WORKFLOW_WORK_DIR 또는 _WF_WORK_DIR 환경변수에서 추출한다.
    추출 실패 시 (워크플로우 외부 호출 등) silently skip.
    모든 예외를 조용히 흡수하여 worktree_manager 동작에 영향을 주지 않는다.

    Args:
        op: 작업 종류 ('create' | 'remove' | 'merge').
        duration_ms: 작업 소요 시간(ms).
        outcome: 결과 ('ok' | 'fail').
        error_reason: 실패 시 예외 메시지 (성공 시 None).
    """
    try:
        work_dir: str | None = None
        for key in ("WORKFLOW_WORK_DIR", "_WF_WORK_DIR"):
            val = os.environ.get(key, "").strip()
            if val and os.path.isdir(val):
                work_dir = val
                break
        if not work_dir:
            return

        payload: dict = {
            "op": op,
            "duration_ms": duration_ms,
            "outcome": outcome,
        }
        if error_reason is not None:
            payload["error_reason"] = str(error_reason)[:500]

        from engine.core.metrics import append_event
        append_event(work_dir, "worktree.io", payload)
    except Exception:  # noqa: BLE001
        pass


# ─── Public API ─────────────────────────────────────────────────────────────────────


def is_worktree_enabled(repo_path: str | None = None) -> bool:
    """worktree 기능 활성화 여부를 판단한다.

    .agent-factory/.settings 의 WORKFLOW_WORKTREE 값을 단일 진실 공급원으로 사용한다 (T-370 후속).

    제거된 폴백 경로:
      - os.environ 의 WORKFLOW_WORKTREE — 환경변수와 .settings 의 이중 진실 공급원으로 인한
        동기화 회귀를 차단한다.
      - develop 브랜치 존재 여부 추론 — 단일 진실 공급원 원칙 준수, 추론 동작 일체 제거.

    부트스트랩 보장: build.sh + claude-env.tmpl 이 .settings 에 WORKFLOW_WORKTREE 항목을
    자동으로 머지한다 (_merge_kv_settings KEY 매칭). 정상 환경에서는 raise 가 발생하지 않는다.

    활성화 표현: "true", "1", "yes", "on" -> True.
    비활성화 표현: "false", "0", "no", "off" -> False.

    Args:
        repo_path: git 저장소 경로 (호환성 유지용 — 현재 미사용).

    Returns:
        worktree 기능 활성화 여부.

    Raises:
        RuntimeError: .settings 에 WORKFLOW_WORKTREE 가 미설정이거나 유효하지 않은 값일 때.
    """
    # .settings Single Source of Truth (T-370 successor) — Remove all inference fallbacks
    setting_val = read_env("WORKFLOW_WORKTREE") or None
    if setting_val is None:
        raise RuntimeError(
            "WORKFLOW_WORKTREE is not set in .agent-factory/.settings."
            "Inference fallbacks (environment variables, presence of develop branch) have been removed in favor of a single source of truth principle."
            "Recovery: Rerun build.sh (automatically enriched with template merge) or"
            "Specify 'WORKFLOW_WORKTREE=true' or 'WORKFLOW_WORKTREE=false' in .settings."
        )

    normalized = setting_val.strip().lower()
    if normalized in ("1", "true", "yes", "on"):
        return True
    if normalized in ("0", "false", "no", "off"):
        return False
    raise RuntimeError(
        f"The WORKFLOW_WORKTREE value is invalid (.settings value: {setting_val!r})."
        "Allowed values: true / false / 1 / 0 / yes / no / on / off"
    )


def create_worktree(
    ticket_number: str,
    title: str,
    base_branch: str = "develop",
    repo_path: str | None = None,
    command: str = "implement",
) -> WorktreeInfo | None:
    """티켓용 worktree를 생성한다.

    develop 브랜치를 확보하고, feature 브랜치를 생성한 후,
    git worktree add로 격리된 작업 디렉터리를 만든다.

    Args:
        ticket_number: 티켓 번호 (예: 'T-001').
        title: 티켓 제목.
        base_branch: 기준 브랜치. 기본값 'develop'.
        repo_path: git 저장소 경로. None이면 프로젝트 루트 사용.
        command: 워크플로우 커맨드. 'implement'가 아니면 생성을 거부한다.

    Returns:
        생성된 WorktreeInfo. 실패 시 None + 경고 출력.
    """
    _t0 = time.monotonic()
    try:
        result = _create_worktree_impl(
            ticket_number, title, base_branch, repo_path, command
        )
        duration_ms = int((time.monotonic() - _t0) * 1000)
        if result is not None:
            _append_worktree_io("create", duration_ms, "ok")
        else:
            _append_worktree_io("create", duration_ms, "fail")
        return result
    except Exception as exc:
        duration_ms = int((time.monotonic() - _t0) * 1000)
        _append_worktree_io("create", duration_ms, "fail", str(exc))
        raise


def _create_worktree_impl(
    ticket_number: str,
    title: str,
    base_branch: str = "develop",
    repo_path: str | None = None,
    command: str = "implement",
) -> WorktreeInfo | None:
    """create_worktree 실제 구현 (metrics timing 래퍼와 분리).

    Args:
        ticket_number: 티켓 번호 (예: 'T-001').
        title: 티켓 제목.
        base_branch: 기준 브랜치. 기본값 'develop'.
        repo_path: git 저장소 경로. None이면 프로젝트 루트 사용.
        command: 워크플로우 커맨드. 'implement'가 아니면 생성을 거부한다.

    Returns:
        생성된 WorktreeInfo. 실패 시 None + 경고 출력.
    """
    # Command defense: Refuse to create worktrees other than implement.
    if command not in ("implement",):
        _warn(
            f"Worktree creation is only for implement workflows"
            f"(requested command: {command})"
        )
        return None

    # Ticket number normalization
    ticket_number = normalize_ticket_number(ticket_number)

    # Secure the develop branch
    if not ensure_develop_branch(repo_path):
        _warn("Failed to create develop branch, unable to create worktree")
        return None

    # Create feature branch
    branch_name = create_feature_branch(
        ticket_number, title, base=base_branch, repo_path=repo_path
    )
    if not branch_name:
        _warn("Feature branch creation failed, unable to create worktree")
        return None

    # worktree directory path
    base_dir = _worktrees_base_dir(repo_path)
    wt_path = str(worktree_path_for_branch(_get_project_root(repo_path), branch_name))

    # Check for already existing worktree
    if os.path.isdir(wt_path):
        _info(f"worktree already exists: {wt_path}")
        return WorktreeInfo(
            path=wt_path,
            branch_name=branch_name,
            ticket_number=ticket_number,
            created_at=datetime.now().isoformat(),
            base_branch=base_branch,
        )

    # Secure parent directory
    os.makedirs(base_dir, exist_ok=True)

    # git worktree add --lock
    git_result = _git(
        "worktree", "add", "--lock", wt_path, branch_name,
        repo_path=repo_path,
    )
    if git_result.returncode != 0:
        _warn(f"Failed to create worktree: {git_result.stderr.strip()}")
        return None

    created_at = datetime.now().isoformat()
    _info(f"Create worktree: {wt_path} (branch: {branch_name})")

    return WorktreeInfo(
        path=wt_path,
        branch_name=branch_name,
        ticket_number=ticket_number,
        created_at=created_at,
        base_branch=base_branch,
    )


def has_uncommitted_changes(worktree_path: str) -> bool:
    """worktree 경로에 미커밋 변경이 있는지 검사한다.

    ``git status --porcelain`` 출력이 비어있지 않으면 미커밋 변경이 있음을
    의미한다. 경로가 존재하지 않거나 git 명령 실행에 실패한 경우 False를
    반환하여 false positive를 방지한다.

    Args:
        worktree_path: 검사할 worktree 디렉터리 경로.

    Returns:
        미커밋 변경이 있으면 True, 없거나 검사 불가 시 False.
    """
    result = _git("status", "--porcelain", repo_path=worktree_path)
    if result.returncode != 0:
        return False
    return bool(result.stdout.strip())


def count_feature_branch_commits(
    branch_name: str,
    base_branch: str = "develop",
    repo_path: str | None = None,
) -> int:
    """feature 브랜치에서 base_branch 이후 누적된 커밋 수를 반환한다.

    ``git rev-list --count <base_branch>..<branch_name>`` 를 실행하여
    feature 브랜치가 base_branch 분기점 이후 만든 커밋 수를 계산한다.

    워커 commit 누락 탐지 신호로 사용된다:
      - 0: 워커가 커밋을 한 건도 만들지 않은 상태 (commit 누락 신호)
      - 양수: 정상 (커밋이 존재)
      - -1: 검사 불가 (브랜치 미존재, base_branch 미존재 등) — 호출자는
            이 경우 차단하지 않고 통과시켜야 한다 (false-positive 방지).

    Args:
        branch_name: 커밋 수를 셀 feature 브랜치명 (예: 'feat/T-001-title').
        base_branch: 기준 브랜치. 기본값 'develop'.
        repo_path: git 저장소 경로. None이면 프로젝트 루트 사용.

    Returns:
        커밋 수 (0 이상의 정수). 검사 불가 시 -1.
    """
    result = _git(
        "rev-list", "--count", f"{base_branch}..{branch_name}",
        repo_path=repo_path,
    )
    if result.returncode != 0:
        return -1
    try:
        return int(result.stdout.strip())
    except (ValueError, AttributeError):
        return -1


def remove_worktree(
    ticket_number: str,
    delete_branch: bool = True,
    repo_path: str | None = None,
) -> bool:
    """티켓에 연결된 worktree를 제거한다.

    멱등 동작: 이미 제거되었으면 True를 반환한다.
    delete_branch=True이면 feature 브랜치도 삭제한다.
    실패 시 False + 경고만 출력하며 프로세스를 종료하지 않는다.

    Args:
        ticket_number: 티켓 번호 (예: 'T-001').
        delete_branch: feature 브랜치도 삭제할지 여부. 기본값 True.
        repo_path: git 저장소 경로. None이면 프로젝트 루트 사용.

    Returns:
        제거 성공(또는 이미 없음) 시 True, 실패 시 False.
    """
    _t0 = time.monotonic()
    try:
        result = _remove_worktree_impl(ticket_number, delete_branch, repo_path)
        duration_ms = int((time.monotonic() - _t0) * 1000)
        outcome = "ok" if result else "fail"
        _append_worktree_io("remove", duration_ms, outcome)
        return result
    except Exception as exc:
        duration_ms = int((time.monotonic() - _t0) * 1000)
        _append_worktree_io("remove", duration_ms, "fail", str(exc))
        raise


def _remove_worktree_impl(
    ticket_number: str,
    delete_branch: bool = True,
    repo_path: str | None = None,
) -> bool:
    """remove_worktree 실제 구현 (metrics timing 래퍼와 분리).

    Args:
        ticket_number: 티켓 번호 (예: 'T-001').
        delete_branch: feature 브랜치도 삭제할지 여부. 기본값 True.
        repo_path: git 저장소 경로. None이면 프로젝트 루트 사용.

    Returns:
        제거 성공(또는 이미 없음) 시 True, 실패 시 False.
    """
    ticket_number = normalize_ticket_number(ticket_number)

    branch_name = get_feature_branch_for_ticket(ticket_number, repo_path)
    if not branch_name:
        # If there is no feature branch, there will be no worktree, so success is processed.
        return True

    wt_path = str(worktree_path_for_branch(_get_project_root(repo_path), branch_name))

    # Unlock the worktree (since you created it with --lock)
    unlock_result = _git("worktree", "unlock", wt_path, repo_path=repo_path)

    # remove worktree
    if os.path.isdir(wt_path):
        if unlock_result.returncode == 0:
            # Unlock success: --force 1 time (force processing of dirty state)
            result = _git(
                "worktree", "remove", "--force", wt_path, repo_path=repo_path
            )
        else:
            # Unlock failure: Assume locked state, --force --force (force locked + dirty processing)
            result = _git(
                "worktree", "remove", "--force", "--force", wt_path,
                repo_path=repo_path,
            )
        if result.returncode != 0:
            _warn(f"Failed to remove worktree: {result.stderr.strip()}")
            return False

    # git worktree prune (prune residual information)
    _git("worktree", "prune", repo_path=repo_path)

    _info(f"Remove worktree: {wt_path}")

    # Delete feature branch
    if delete_branch and branch_name:
        delete_feature_branch(branch_name, repo_path)

    return True


def merge_to_develop(
    ticket_number: str, repo_path: str | None = None
) -> MergeResult:
    """feature 브랜치를 develop에 --no-ff 병합한다.

    mkdir 기반 잠금으로 동시 병합을 방지하며, 충돌 시 자동으로
    git merge --abort를 수행한다. 병합 성공 후 worktree와
    feature 브랜치를 정리한다.

    Args:
        ticket_number: 티켓 번호 (예: 'T-001').
        repo_path: git 저장소 경로. None이면 프로젝트 루트 사용.

    Returns:
        MergeResult 인스턴스.
    """
    _t0 = time.monotonic()
    try:
        merge_result = _merge_to_develop_impl(ticket_number, repo_path)
        duration_ms = int((time.monotonic() - _t0) * 1000)
        outcome = "ok" if merge_result.success else "fail"
        error_reason = merge_result.error_message if not merge_result.success else None
        _append_worktree_io("merge", duration_ms, outcome, error_reason)
        return merge_result
    except Exception as exc:
        duration_ms = int((time.monotonic() - _t0) * 1000)
        _append_worktree_io("merge", duration_ms, "fail", str(exc))
        raise


def _merge_to_develop_impl(
    ticket_number: str, repo_path: str | None = None
) -> MergeResult:
    """merge_to_develop 실제 구현 (metrics timing 래퍼와 분리).

    Args:
        ticket_number: 티켓 번호 (예: 'T-001').
        repo_path: git 저장소 경로. None이면 프로젝트 루트 사용.

    Returns:
        MergeResult 인스턴스.
    """
    ticket_number = normalize_ticket_number(ticket_number)

    # When called in an environment where WORKFLOW_WORKTREE=false, the main storage HEAD is
    # Instructs users on the manual merge command.
    if not is_worktree_enabled(repo_path):
        _warn(
            "merge_to_develop() in non-worktree mode (WORKFLOW_WORKTREE=false)"
            "You have been called. Main storage HEAD is blocked to prevent contamination."
        )
        _warn(
            "Manual merge procedure:"
            "git checkout develop && "
            f"git merge --no-ff <feature-branch-of-{ticket_number}>"
        )
        return MergeResult(
            success=False,
            error_message=(
                f"Non-worktree mode — merge_to_develop({ticket_number}) blocked."
                "WORKFLOW_WORKTREE=true Requires activation or manual merge."
            ),
        )

    branch_name = get_feature_branch_for_ticket(ticket_number, repo_path)
    if not branch_name:
        return MergeResult(
            success=False,
            error_message=f"The feature branch linked to {ticket_number} could not be found",
        )

    lock_path = _merge_lock_path(repo_path)
    original_branch = _get_current_branch(repo_path)

    # acquire lock
    if not acquire_lock(lock_path, max_wait=10, stale_timeout=300):
        return MergeResult(
            success=False,
            error_message="Failed to acquire merge lock (another merge may be in progress)",
        )

    try:
        # Secure the develop branch
        if not ensure_develop_branch(repo_path):
            return MergeResult(
                success=False,
                error_message="Failed to create develop branch",
            )

        # develop checkout
        checkout_result = _git("checkout", "develop", repo_path=repo_path)
        if checkout_result.returncode != 0:
            return MergeResult(
                success=False,
                error_message=f"develop checkout failed: {checkout_result.stderr.strip()}",
            )

        # --no-ff merge
        merge_msg = f"Merge {branch_name} into develop"
        merge_result = _git(
            "merge", "--no-ff", "-m", merge_msg, branch_name,
            repo_path=repo_path,
        )

        if merge_result.returncode != 0:
            # collision detection
            conflicts = _detect_conflicts(repo_path)
            # merge --abort
            _git("merge", "--abort", repo_path=repo_path)

            return MergeResult(
                success=False,
                conflicts=conflicts,
                merged_branch=branch_name,
                error_message=f"Merge conflicts occur: {', '.join(conflicts) if conflicts else merge_result.stderr.strip()}",
            )

        # Obtain merge commit SHA
        sha_result = _git("rev-parse", "HEAD", repo_path=repo_path)
        merge_commit = sha_result.stdout.strip() if sha_result.returncode == 0 else ""

        _info(f"Merge successful: {branch_name} -> develop ({merge_commit[:8]})")

        # Organize worktree + feature branches
        remove_worktree(ticket_number, delete_branch=True, repo_path=repo_path)

        return MergeResult(
            success=True,
            merged_branch=branch_name,
            merge_commit=merge_commit,
        )

    finally:
        # Restore original branch (if not develop)
        if original_branch and original_branch != "develop":
            # If the original branch has been deleted (the feature branch you just merged and cleaned up)
            # It's safe to remain in develop
            restore_result = _git(
                "checkout", original_branch, repo_path=repo_path
            )
            if restore_result.returncode != 0:
                # Stay in develop if original branch restoration fails
                _warn(
                    f"Failed to restore original branch ({original_branch}),"
                    f"keep in develop"
                )

        # unlocked
        release_lock(lock_path)


_PORCELAIN_CONFLICT_CODES: frozenset[str] = frozenset(
    {"UU", "AA", "DD", "AU", "UA", "DU", "UD"}
)
"""Set of conflicting codes from git status --porcelain ."""

_SENTINEL_UNKNOWN_CONFLICT: str = "<unknown-conflict>"
"""The sentinel value returned when both git sources fail."""


def _parse_porcelain_conflicts(stdout: str) -> list[str]:
    """``git status --porcelain`` 출력에서 충돌 파일 목록을 파싱한다.

    XY 형식의 porcelain 상태 코드 중 충돌 코드(UU, AA, DD, AU, UA, DU, UD)가
    포함된 행만 필터링하여 파일 경로를 반환한다.

    Args:
        stdout: ``git status --porcelain`` 의 표준 출력 문자열.

    Returns:
        충돌 파일 경로 목록. 충돌 없으면 빈 리스트.

    Examples:
        >>> _parse_porcelain_conflicts("UU foo.py\\nAA bar.py\\n M baz.py\\n")
        ['foo.py', 'bar.py']
    """
    conflicts: list[str] = []
    for line in stdout.splitlines():
        if len(line) < 4:
            continue
        # porcelain v1 format: "XY <path>" (XY = 2 characters, 1 space, path)
        xy = line[:2]
        path = line[3:].strip()
        if xy in _PORCELAIN_CONFLICT_CODES and path:
            conflicts.append(path)
    return conflicts


def _detect_conflicts(repo_path: str | None = None) -> list[str]:
    """병합 충돌 파일 목록을 반환한다.

    두 단계 소스로 충돌 파일을 탐지하며, 모든 소스 실패 시 sentinel을 반환한다.

    | 단계 | 소스 | 조건 |
    |------|------|------|
    | 1차  | ``git diff --name-only --diff-filter=U`` | 항상 시도. 결과 비면 2차로 진행 |
    | 2차  | ``git status --porcelain`` (UU/AA/DD/AU/UA/DU/UD) | 1차 결과가 빈 리스트일 때만 시도 |
    | sentinel | ``["<unknown-conflict>"]`` | 두 소스 모두 returncode != 0 일 때 반환 |

    1차 소스가 결과를 반환하면 바로 리턴(2차 시도 없음).
    1차 성공 + 빈 리스트이면 2차 시도. 2차도 성공하면 두 결과의 합집합(중복 제거).
    1차와 2차 모두 returncode != 0 이면 ``["<unknown-conflict>"]`` sentinel 반환.

    sentinel 의미: 충돌이 발생했지만 파일 목록을 확인할 수 없는 상태.
    호출자는 ``"<unknown-conflict>" in conflicts`` 로 sentinel을 구분할 수 있다.

    Args:
        repo_path: git 저장소 경로.

    Returns:
        충돌 파일 경로 목록. 모든 git 명령 실패 시 sentinel ``["<unknown-conflict>"]``.
    """
    # Primary source: git diff --name-only --diff-filter=U
    diff_result = _git(
        "diff", "--name-only", "--diff-filter=U", repo_path=repo_path
    )
    diff_ok = diff_result.returncode == 0
    diff_files: list[str] = []
    if diff_ok:
        diff_files = [
            line.strip()
            for line in diff_result.stdout.splitlines()
            if line.strip()
        ]
        if diff_files:
            # If there is a result in the primary source, it is returned immediately
            return diff_files

    # Secondary source: git status --porcelain (when primary is empty list or fails)
    porcelain_result = _git("status", "--porcelain", repo_path=repo_path)
    porcelain_ok = porcelain_result.returncode == 0

    if not diff_ok and not porcelain_ok:
        # Both sources fail → sentinel returns
        return [_SENTINEL_UNKNOWN_CONFLICT]

    porcelain_files: list[str] = []
    if porcelain_ok:
        porcelain_files = _parse_porcelain_conflicts(porcelain_result.stdout)

    # Union (1st result + 2nd result, maintain order + remove duplicates)
    seen: set[str] = set()
    merged: list[str] = []
    for f in diff_files + porcelain_files:
        if f not in seen:
            seen.add(f)
            merged.append(f)
    return merged


def list_worktrees(repo_path: str | None = None) -> list[WorktreeInfo]:
    """활성 worktree 목록을 반환한다.

    git worktree list --porcelain 출력을 파싱하여 프로젝트 내
    feature worktree만 필터링한다.

    Args:
        repo_path: git 저장소 경로. None이면 프로젝트 루트 사용.

    Returns:
        WorktreeInfo 리스트. 파싱 실패 시 빈 리스트.
    """
    result = _git("worktree", "list", "--porcelain", repo_path=repo_path)
    if result.returncode != 0:
        return []

    worktrees: list[WorktreeInfo] = []
    base_dir = _worktrees_base_dir(repo_path)

    # Parsing porcelain output: blocks separated by blank lines
    current: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if not line.strip():
            wt_info = _parse_worktree_block(current, base_dir)
            if wt_info:
                worktrees.append(wt_info)
            current = {}
            continue

        if line.startswith("worktree "):
            current["path"] = line[len("worktree "):]
        elif line.startswith("branch "):
            current["branch"] = line[len("branch "):]

    # Last block processing
    if current:
        wt_info = _parse_worktree_block(current, base_dir)
        if wt_info:
            worktrees.append(wt_info)

    return worktrees


def _parse_worktree_block(
    block: dict[str, str], base_dir: str
) -> WorktreeInfo | None:
    """porcelain 블록을 WorktreeInfo로 파싱한다.

    feature worktree만 반환하며 (feat/T-NNN-* 패턴), 메인 worktree는
    필터링한다.

    Args:
        block: porcelain 파싱 중간 결과 딕셔너리.
        base_dir: .worktrees/ 디렉터리 절대 경로.

    Returns:
        WorktreeInfo 또는 None (feature worktree가 아닌 경우).
    """
    wt_path = block.get("path", "")
    branch_ref = block.get("branch", "")

    if not wt_path or not branch_ref:
        return None

    # Remove refs/heads/
    branch_name = branch_ref
    if branch_name.startswith("refs/heads/"):
        branch_name = branch_name[len("refs/heads/"):]

    # Filter only feature branches
    match = re.match(r"^feat/(T-\d+)-", branch_name)
    if not match:
        return None

    ticket_number = match.group(1)

    return WorktreeInfo(
        path=wt_path,
        branch_name=branch_name,
        ticket_number=ticket_number,
        created_at="",  # porcelain output has no creation time
    )


def get_worktree_path(
    ticket_number: str, repo_path: str | None = None
) -> str | None:
    """티켓에 연결된 worktree 절대 경로를 반환한다.

    list_worktrees() 결과에서 티켓 번호로 검색하거나,
    feature 브랜치명으로 경로를 추론한다.

    Args:
        ticket_number: 티켓 번호 (예: 'T-001').
        repo_path: git 저장소 경로. None이면 프로젝트 루트 사용.

    Returns:
        worktree 절대 경로 또는 None.
    """
    ticket_number = normalize_ticket_number(ticket_number)

    # Search in list of active worktrees
    for wt in list_worktrees(repo_path):
        if wt.ticket_number == ticket_number:
            return wt.path

    # If not in the list, infer the path using the feature branch name.
    branch_name = get_feature_branch_for_ticket(ticket_number, repo_path)
    if branch_name:
        candidate = str(
            worktree_path_for_branch(_get_project_root(repo_path), branch_name)
        )
        if os.path.isdir(candidate):
            return candidate

    return None
