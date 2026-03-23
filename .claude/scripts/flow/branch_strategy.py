"""branch_strategy.py - Git 브랜치 전략 관리 모듈.

워크플로우별 feature 브랜치 생성/삭제/검색 및 develop/main 브랜치
감지를 담당한다. worktree_manager.py의 기반 모듈이다.

공개 API:
    get_main_branch: main 또는 master 브랜치 감지
    ensure_develop_branch: develop 브랜치 확보 (없으면 로컬 생성)
    create_feature_branch: feat/T-NNN-제목 브랜치 생성
    delete_feature_branch: feature 브랜치 삭제 (로컬)
    sanitize_branch_name: 브랜치명 안전 변환
    get_feature_branch_for_ticket: 티켓에 연결된 feature 브랜치 검색
"""

from __future__ import annotations

import os
import re
import subprocess
import sys

# ─── sys.path 보장 ────────────────────────────────────────────────────────────

_scripts_dir: str = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
)
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from common import resolve_project_root

# ─── 상수 ─────────────────────────────────────────────────────────────────────

_BRANCH_NAME_MAX_LEN: int = 50
_FEATURE_PREFIX: str = "feat/"

# git 브랜치명에 사용 불가한 문자 패턴 (한글은 허용)
# ~ ^ : ? * [ \ 및 공백, 제어문자, DEL
_GIT_FORBIDDEN_CHARS: re.Pattern[str] = re.compile(r"[~^:?*\[\]\\@{}\x00-\x1f\x7f]")


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
    return subprocess.run(
        cmd, capture_output=True, text=True, timeout=30
    )


def _get_local_branches(repo_path: str | None = None) -> list[str]:
    """로컬 브랜치 목록을 반환한다.

    Args:
        repo_path: git 저장소 경로. None이면 프로젝트 루트 사용.

    Returns:
        로컬 브랜치명 리스트 (refs/heads/ 제외).
    """
    result = _git("branch", "--list", "--format=%(refname:short)", repo_path=repo_path)
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _warn(msg: str) -> None:
    """경고 메시지를 stderr로 출력한다."""
    print(f"[WARN] branch_strategy: {msg}", file=sys.stderr)


# ─── 공개 API ─────────────────────────────────────────────────────────────────


def sanitize_branch_name(raw: str) -> str:
    """브랜치명을 git 안전 형식으로 변환한다.

    한글은 허용하며, 공백/언더스코어를 하이픈으로 변환하고
    git 금지 문자를 제거한다. 연속 하이픈은 단일화하며
    최대 50자로 제한한다.

    Args:
        raw: 원본 문자열 (티켓 제목 등).

    Returns:
        git 브랜치명에 안전한 문자열 (최대 50자).
    """
    name: str = raw.strip()

    # 공백, 언더스코어 → 하이픈
    name = re.sub(r"[\s_]+", "-", name)

    # git 금지 문자 제거
    name = _GIT_FORBIDDEN_CHARS.sub("", name)

    # 점(.)으로 시작/끝나거나 연속 점(..) 방지
    name = re.sub(r"\.{2,}", ".", name)

    # 슬래시 제거 (feature prefix 외 슬래시 방지)
    name = name.replace("/", "-")

    # 연속 하이픈 → 단일 하이픈
    name = re.sub(r"-{2,}", "-", name)

    # 선행/후행 하이픈, 점 제거
    name = name.strip("-.")

    # 최대 길이 제한
    if len(name) > _BRANCH_NAME_MAX_LEN:
        name = name[:_BRANCH_NAME_MAX_LEN].rstrip("-.")

    return name


def get_main_branch(repo_path: str | None = None) -> str:
    """main 또는 master 브랜치를 감지하여 반환한다.

    로컬 브랜치 목록에서 'main'을 먼저 찾고, 없으면 'master'를 찾는다.
    둘 다 없으면 기본값 'main'을 반환한다.

    Args:
        repo_path: git 저장소 경로. None이면 프로젝트 루트 사용.

    Returns:
        감지된 메인 브랜치명 ('main' 또는 'master'). 둘 다 없으면 'main'.
    """
    branches = _get_local_branches(repo_path)
    if "main" in branches:
        return "main"
    if "master" in branches:
        return "master"
    return "main"


def ensure_develop_branch(repo_path: str | None = None) -> bool:
    """develop 브랜치가 없으면 main 기준으로 로컬 생성한다.

    이미 develop 브랜치가 존재하면 아무 작업도 하지 않고 True를 반환한다.
    없으면 main/master 브랜치 기준으로 develop 브랜치를 생성한다.

    Args:
        repo_path: git 저장소 경로. None이면 프로젝트 루트 사용.

    Returns:
        develop 브랜치가 존재하거나 성공적으로 생성되면 True.
        생성 실패 시 False.
    """
    branches = _get_local_branches(repo_path)
    if "develop" in branches:
        return True

    main_branch = get_main_branch(repo_path)
    result = _git("branch", "develop", main_branch, repo_path=repo_path)
    if result.returncode != 0:
        _warn(f"develop 브랜치 생성 실패: {result.stderr.strip()}")
        return False
    return True


def create_feature_branch(
    ticket_number: str,
    title: str,
    base: str = "develop",
    repo_path: str | None = None,
) -> str:
    """feature 브랜치를 생성하고 브랜치명을 반환한다.

    feat/T-NNN-제목 형식의 브랜치를 base 브랜치 기준으로 생성한다.
    이미 동일 티켓의 feature 브랜치가 존재하면 기존 브랜치명을 반환한다.

    Args:
        ticket_number: 티켓 번호 (예: 'T-001', '001').
        title: 티켓 제목. sanitize_branch_name으로 정제된다.
        base: 기준 브랜치. 기본값 'develop'.
        repo_path: git 저장소 경로. None이면 프로젝트 루트 사용.

    Returns:
        생성된 또는 기존 feature 브랜치명 (예: 'feat/T-001-제목').
        생성 실패 시 빈 문자열.
    """
    # 티켓 번호 정규화: 'T-001' 형식 보장
    if not ticket_number.startswith("T-"):
        ticket_number = f"T-{ticket_number}"

    # 기존 feature 브랜치 검색
    existing = get_feature_branch_for_ticket(ticket_number, repo_path)
    if existing:
        return existing

    sanitized = sanitize_branch_name(title)
    branch_name = f"{_FEATURE_PREFIX}{ticket_number}-{sanitized}"

    result = _git("branch", branch_name, base, repo_path=repo_path)
    if result.returncode != 0:
        _warn(f"feature 브랜치 생성 실패: {result.stderr.strip()}")
        return ""

    return branch_name


def delete_feature_branch(
    branch_name: str, repo_path: str | None = None
) -> bool:
    """로컬 feature 브랜치를 삭제한다.

    강제 삭제(-D)를 사용하며, 삭제 실패 시 경고만 출력하고
    False를 반환한다 (프로세스 종료하지 않음).

    Args:
        branch_name: 삭제할 브랜치명 (예: 'feat/T-001-제목').
        repo_path: git 저장소 경로. None이면 프로젝트 루트 사용.

    Returns:
        삭제 성공 시 True, 실패 시 False.
    """
    result = _git("branch", "-D", branch_name, repo_path=repo_path)
    if result.returncode != 0:
        _warn(f"브랜치 삭제 실패 ({branch_name}): {result.stderr.strip()}")
        return False
    return True


def get_feature_branch_for_ticket(
    ticket_number: str, repo_path: str | None = None
) -> str | None:
    """티켓 번호에 연결된 feature 브랜치를 검색한다.

    로컬 브랜치 중 'feat/T-NNN-*' 패턴과 일치하는 첫 번째 브랜치를
    반환한다. 없으면 None.

    Args:
        ticket_number: 티켓 번호 (예: 'T-001').
        repo_path: git 저장소 경로. None이면 프로젝트 루트 사용.

    Returns:
        일치하는 브랜치명 또는 None.
    """
    if not ticket_number.startswith("T-"):
        ticket_number = f"T-{ticket_number}"

    prefix = f"{_FEATURE_PREFIX}{ticket_number}-"
    branches = _get_local_branches(repo_path)
    for branch in branches:
        if branch.startswith(prefix):
            return branch
    return None
