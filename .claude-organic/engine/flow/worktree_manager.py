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
from dataclasses import dataclass, field
from datetime import datetime

# ─── sys.path 보장 ────────────────────────────────────────────────────────────

_engine_dir: str = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
)
if _engine_dir not in sys.path:
    sys.path.insert(0, _engine_dir)

from common import acquire_lock, read_env, release_lock, resolve_project_root
from flow.branch_strategy import (
    create_feature_branch,
    delete_feature_branch,
    ensure_develop_branch,
    get_feature_branch_for_ticket,
)

# ─── 상수 ─────────────────────────────────────────────────────────────────────

_WORKTREES_DIR_NAME: str = os.path.join(".claude-organic", "worktrees")
_MERGE_LOCK_NAME: str = "worktree-merge.lockdir"


# ─── 데이터 클래스 ────────────────────────────────────────────────────────────


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


# ─── 내부 유틸리티 ────────────────────────────────────────────────────────────


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


def _get_project_root(repo_path: str | None = None) -> str:
    """프로젝트 루트 절대 경로를 반환한다."""
    return repo_path or resolve_project_root()


def _worktrees_base_dir(repo_path: str | None = None) -> str:
    """worktree가 저장되는 상위 디렉터리 경로를 반환한다.

    Returns:
        프로젝트 루트 아래 .worktrees/ 절대 경로.
    """
    root = _get_project_root(repo_path)
    return os.path.join(root, _WORKTREES_DIR_NAME)


def _merge_lock_path(repo_path: str | None = None) -> str:
    """병합 잠금 디렉터리 경로를 반환한다.

    Returns:
        .git/worktree-merge.lockdir 절대 경로.
    """
    root = _get_project_root(repo_path)
    return os.path.join(root, ".git", _MERGE_LOCK_NAME)


def _worktree_dir_name(branch_name: str) -> str:
    """브랜치명을 worktree 디렉터리명으로 변환한다.

    feat/T-NNN-제목 -> feat-T-NNN-제목 (슬래시를 하이픈으로).

    Args:
        branch_name: feature 브랜치명.

    Returns:
        디렉터리명 (슬래시 없음).
    """
    return branch_name.replace("/", "-")


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
    """경고 메시지를 stderr로 출력한다."""
    print(f"[WARN] worktree_manager: {msg}", file=sys.stderr)


def _info(msg: str) -> None:
    """정보 메시지를 stderr로 출력한다."""
    print(f"[INFO] worktree_manager: {msg}", file=sys.stderr)


# ─── 공개 API ─────────────────────────────────────────────────────────────────


def is_worktree_enabled(repo_path: str | None = None) -> bool:
    """worktree 기능 활성화 여부를 판단한다.

    WORKFLOW_WORKTREE 환경변수가 os.environ에 설정되어 있으면 그 값으로
    판단한다. os.environ에 없으면 .settings 파일에서 폴백 읽기를 수행한다.
    활성화 표현: "true", "1", "yes", "on" -> True.
    비활성화 표현: "false", "0", "no", "off" -> False.
    os.environ과 .settings 모두 미설정 시 develop 브랜치 존재 여부로 판단한다.

    Args:
        repo_path: git 저장소 경로. None이면 프로젝트 루트 사용.

    Returns:
        worktree 기능 활성화 여부.
    """
    env_val = os.environ.get("WORKFLOW_WORKTREE")
    if env_val is None:
        # os.environ에 없으면 .settings 파일에서 폴백 읽기
        env_val = read_env("WORKFLOW_WORKTREE") or None

    if env_val is not None:
        normalized = env_val.strip().lower()
        if normalized in ("1", "true", "yes", "on"):
            return True
        if normalized in ("0", "false", "no", "off"):
            return False

    # 환경변수 미설정: develop 브랜치 존재 여부
    result = _git(
        "rev-parse", "--verify", "refs/heads/develop", repo_path=repo_path
    )
    return result.returncode == 0


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
    # command 방어: implement 외에는 worktree 생성을 거부한다
    if command not in ("implement",):
        _warn(
            f"worktree 생성은 implement 워크플로우 전용입니다 "
            f"(요청된 command: {command})"
        )
        return None

    # 티켓 번호 정규화
    if not ticket_number.startswith("T-"):
        ticket_number = f"T-{ticket_number}"

    # develop 브랜치 확보
    if not ensure_develop_branch(repo_path):
        _warn("develop 브랜치 생성 실패, worktree를 만들 수 없습니다")
        return None

    # feature 브랜치 생성
    branch_name = create_feature_branch(
        ticket_number, title, base=base_branch, repo_path=repo_path
    )
    if not branch_name:
        _warn("feature 브랜치 생성 실패, worktree를 만들 수 없습니다")
        return None

    # worktree 디렉터리 경로
    dir_name = _worktree_dir_name(branch_name)
    base_dir = _worktrees_base_dir(repo_path)
    wt_path = os.path.join(base_dir, dir_name)

    # 이미 존재하는 worktree 확인
    if os.path.isdir(wt_path):
        _info(f"worktree 이미 존재: {wt_path}")
        return WorktreeInfo(
            path=wt_path,
            branch_name=branch_name,
            ticket_number=ticket_number,
            created_at=datetime.now().isoformat(),
            base_branch=base_branch,
        )

    # 상위 디렉터리 확보
    os.makedirs(base_dir, exist_ok=True)

    # git worktree add --lock
    result = _git(
        "worktree", "add", "--lock", wt_path, branch_name,
        repo_path=repo_path,
    )
    if result.returncode != 0:
        _warn(f"worktree 생성 실패: {result.stderr.strip()}")
        return None

    created_at = datetime.now().isoformat()
    _info(f"worktree 생성: {wt_path} (branch: {branch_name})")

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
    if not ticket_number.startswith("T-"):
        ticket_number = f"T-{ticket_number}"

    branch_name = get_feature_branch_for_ticket(ticket_number, repo_path)
    if not branch_name:
        # feature 브랜치가 없으면 worktree도 없을 것이므로 성공 처리
        return True

    dir_name = _worktree_dir_name(branch_name)
    base_dir = _worktrees_base_dir(repo_path)
    wt_path = os.path.join(base_dir, dir_name)

    # worktree 잠금 해제 (--lock으로 생성했으므로)
    unlock_result = _git("worktree", "unlock", wt_path, repo_path=repo_path)

    # worktree 제거
    if os.path.isdir(wt_path):
        if unlock_result.returncode == 0:
            # unlock 성공: --force 1회 (dirty 상태 강제 처리)
            result = _git(
                "worktree", "remove", "--force", wt_path, repo_path=repo_path
            )
        else:
            # unlock 실패: locked 상태 가정, --force --force (locked + dirty 강제 처리)
            result = _git(
                "worktree", "remove", "--force", "--force", wt_path,
                repo_path=repo_path,
            )
        if result.returncode != 0:
            _warn(f"worktree 제거 실패: {result.stderr.strip()}")
            return False

    # git worktree prune (잔여 정보 정리)
    _git("worktree", "prune", repo_path=repo_path)

    _info(f"worktree 제거: {wt_path}")

    # feature 브랜치 삭제
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
    if not ticket_number.startswith("T-"):
        ticket_number = f"T-{ticket_number}"

    branch_name = get_feature_branch_for_ticket(ticket_number, repo_path)
    if not branch_name:
        return MergeResult(
            success=False,
            error_message=f"{ticket_number}에 연결된 feature 브랜치를 찾을 수 없습니다",
        )

    lock_path = _merge_lock_path(repo_path)
    original_branch = _get_current_branch(repo_path)

    # 잠금 획득
    if not acquire_lock(lock_path, max_wait=10, stale_timeout=300):
        return MergeResult(
            success=False,
            error_message="병합 잠금 획득 실패 (다른 병합이 진행 중일 수 있습니다)",
        )

    try:
        # develop 브랜치 확보
        if not ensure_develop_branch(repo_path):
            return MergeResult(
                success=False,
                error_message="develop 브랜치 생성 실패",
            )

        # develop checkout
        checkout_result = _git("checkout", "develop", repo_path=repo_path)
        if checkout_result.returncode != 0:
            return MergeResult(
                success=False,
                error_message=f"develop checkout 실패: {checkout_result.stderr.strip()}",
            )

        # --no-ff 병합
        merge_msg = f"Merge {branch_name} into develop"
        merge_result = _git(
            "merge", "--no-ff", "-m", merge_msg, branch_name,
            repo_path=repo_path,
        )

        if merge_result.returncode != 0:
            # 충돌 감지
            conflicts = _detect_conflicts(repo_path)
            # merge --abort
            _git("merge", "--abort", repo_path=repo_path)

            return MergeResult(
                success=False,
                conflicts=conflicts,
                merged_branch=branch_name,
                error_message=f"병합 충돌 발생: {', '.join(conflicts) if conflicts else merge_result.stderr.strip()}",
            )

        # 병합 커밋 SHA 획득
        sha_result = _git("rev-parse", "HEAD", repo_path=repo_path)
        merge_commit = sha_result.stdout.strip() if sha_result.returncode == 0 else ""

        _info(f"병합 성공: {branch_name} -> develop ({merge_commit[:8]})")

        # worktree + feature 브랜치 정리
        remove_worktree(ticket_number, delete_branch=True, repo_path=repo_path)

        return MergeResult(
            success=True,
            merged_branch=branch_name,
            merge_commit=merge_commit,
        )

    finally:
        # 원래 브랜치 복원 (develop이 아닌 경우)
        if original_branch and original_branch != "develop":
            # 원래 브랜치가 삭제된 경우 (방금 병합 후 정리한 feature 브랜치)
            # develop에 남아있는 것이 안전함
            restore_result = _git(
                "checkout", original_branch, repo_path=repo_path
            )
            if restore_result.returncode != 0:
                # 원래 브랜치 복원 실패 시 develop에 유지
                _warn(
                    f"원래 브랜치 복원 실패 ({original_branch}), "
                    f"develop에 유지합니다"
                )

        # 잠금 해제
        release_lock(lock_path)


def _detect_conflicts(repo_path: str | None = None) -> list[str]:
    """병합 충돌 파일 목록을 반환한다.

    Args:
        repo_path: git 저장소 경로.

    Returns:
        충돌 파일 경로 목록.
    """
    result = _git("diff", "--name-only", "--diff-filter=U", repo_path=repo_path)
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


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

    # porcelain 출력 파싱: 빈 줄로 구분된 블록
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

    # 마지막 블록 처리
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

    # refs/heads/ 제거
    branch_name = branch_ref
    if branch_name.startswith("refs/heads/"):
        branch_name = branch_name[len("refs/heads/"):]

    # feature 브랜치만 필터링
    match = re.match(r"^feat/(T-\d+)-", branch_name)
    if not match:
        return None

    ticket_number = match.group(1)

    return WorktreeInfo(
        path=wt_path,
        branch_name=branch_name,
        ticket_number=ticket_number,
        created_at="",  # porcelain 출력에는 생성 시각 없음
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
    if not ticket_number.startswith("T-"):
        ticket_number = f"T-{ticket_number}"

    # 활성 worktree 목록에서 검색
    for wt in list_worktrees(repo_path):
        if wt.ticket_number == ticket_number:
            return wt.path

    # 목록에 없으면 feature 브랜치명으로 경로 추론
    branch_name = get_feature_branch_for_ticket(ticket_number, repo_path)
    if branch_name:
        dir_name = _worktree_dir_name(branch_name)
        candidate = os.path.join(_worktrees_base_dir(repo_path), dir_name)
        if os.path.isdir(candidate):
            return candidate

    return None
