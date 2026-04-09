#!/usr/bin/env -S python3 -u
"""워크트리 경로 격리 가드 Hook 스크립트.

PreToolUse(Write|Edit|Bash) 이벤트에서 현재 세션이 워크플로우 세션이고
활성 워크플로우의 command가 implement이면,
메인 리포 경로 파일 수정 시도를 차단하고 워크트리 절대경로를 피드백에 포함한다.

Claude Code가 세션 시작 시 프로젝트 루트(메인 리포)를 cwd로 결정하여
워크트리 경로 대신 메인 리포 경로를 기준으로 파일 수정을 시도하는 문제를
PreToolUse 훅 레이어에서 차단하는 방어 계층(Defense-in-depth)이다.

주요 함수:
    main: Hook 진입점, stdin JSON 파싱 후 메인 리포 경로 수정 차단

입력: stdin으로 JSON (tool_name, tool_input)
출력: 차단 시 hookSpecificOutput JSON, 통과 시 빈 출력

토글: 환경변수 HOOK_WORKTREE_PATH_GUARD (false/0 = 비활성, 기본 활성)
"""

from __future__ import annotations

import json
import os
import re
import sys

# utils 패키지 import 경로 설정
_scripts_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

# prompt 패키지 import 경로 설정
_prompt_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../prompt"))
if _prompt_dir not in sys.path:
    sys.path.insert(0, _prompt_dir)

from common import load_json_file, read_env, resolve_project_root, scan_active_workflows
from flow.session_identifier import get_session_type
from messages import (
    WORKTREE_PATH_BASH_MODIFY_DENIED,
    WORKTREE_PATH_WRITE_EDIT_DENIED,
)

# implement command: 워크트리 격리가 적용되는 command
_IMPLEMENT_COMMAND = "implement"

# Bash 도구에서 파일을 수정할 수 있는 명령 패턴 (readonly_session_guard.py와 동일)
_BASH_FILE_MODIFY_PATTERNS: list[str] = [
    r"\bsed\s+-i",                               # sed inplace
    r"\bawk\s+.*-i\s+inplace",                   # awk inplace
    r"\b(echo|printf)\s+.*\s*>{1,2}\s*\S",       # echo/printf 리다이렉트
    r"\btee\s+(-a\s+)?\S",                       # tee 쓰기
    r"\bcat\s*<<",                               # heredoc 리다이렉트
    r"\bcp\s+",                                  # 파일 복사
    r"\bmv\s+",                                  # 파일 이동
    r"\bpython3?\s+(-c\s+|.*\bopen\b.*\bwrite\b)",  # python -c open write
    r"\bperl\s+-.*[pi]",                         # perl inplace
    r"(?:^|[;&|]\s*)\binstall\s+",               # install 명령 (서브커맨드 제외)
    r"\bdd\s+",                                  # dd 명령
]

# 항상 허용하는 경로 패턴 (.claude.workflow/ 하위 — workflow/, kanban/ 등 포함)
_ALWAYS_ALLOWED_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"[/\\]?\.claude\.workflow[/\\]"),
]


def _deny(reason: str) -> None:
    """차단 JSON을 stdout에 출력하고 프로세스를 종료한다.

    Args:
        reason: 차단 사유 문자열
    """
    result = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0)


def _get_workflow_command() -> str | None:
    """활성 워크플로우의 command 필드를 반환한다.

    WORKFLOW_WORK_DIR 환경변수를 먼저 확인하고,
    없으면 .workflow/ 디렉터리를 스캔하여 가장 최근 .context.json을 읽는다.

    Returns:
        command 문자열. 조회 실패 시 None.
    """
    project_root = resolve_project_root()

    # 1. WORKFLOW_WORK_DIR 환경변수 확인
    env_work_dir = os.environ.get("WORKFLOW_WORK_DIR", "").strip()
    if env_work_dir:
        abs_work_dir = (
            os.path.join(project_root, env_work_dir)
            if not os.path.isabs(env_work_dir)
            else env_work_dir
        )
        ctx = load_json_file(os.path.join(abs_work_dir, ".context.json"))
        if ctx and isinstance(ctx, dict):
            command = ctx.get("command", "")
            if command:
                return command

    # 2. .workflow/ 디렉터리 스캔
    try:
        registry = scan_active_workflows(project_root=project_root)
        if not registry:
            return None

        # updated_at 기준 가장 최근 워크플로우 선택
        best_entry = None
        best_updated = ""
        for _key, entry in registry.items():
            work_dir = entry.get("workDir", "")
            abs_wd = (
                os.path.join(project_root, work_dir)
                if not os.path.isabs(work_dir)
                else work_dir
            )
            status = load_json_file(os.path.join(abs_wd, "status.json"))
            updated_at = status.get("updated_at", "") if isinstance(status, dict) else ""
            if updated_at >= best_updated:
                best_updated = updated_at
                best_entry = entry

        if best_entry:
            return best_entry.get("command", "") or None
    except Exception:
        pass

    return None


def _get_worktree_path() -> str | None:
    """현재 워크플로우 세션의 워크트리 절대경로를 반환한다.

    다음 순서로 워크트리 경로를 탐색한다:
    1. WORKFLOW_WORKTREE_PATH 환경변수
    2. WORKFLOW_WORK_DIR 환경변수 -> .context.json -> worktree.absPath
    3. .workflow/ 디렉터리 스캔 -> .context.json -> worktree.absPath

    Returns:
        워크트리 절대경로 문자열. 탐색 실패 또는 경로가 없으면 None.
    """
    # 1. WORKFLOW_WORKTREE_PATH 환경변수 우선
    env_worktree_path = os.environ.get("WORKFLOW_WORKTREE_PATH", "").strip()
    if env_worktree_path:
        return env_worktree_path

    project_root = resolve_project_root()

    # 2. WORKFLOW_WORK_DIR 환경변수 -> .context.json
    env_work_dir = os.environ.get("WORKFLOW_WORK_DIR", "").strip()
    if env_work_dir:
        abs_work_dir = (
            os.path.join(project_root, env_work_dir)
            if not os.path.isabs(env_work_dir)
            else env_work_dir
        )
        ctx = load_json_file(os.path.join(abs_work_dir, ".context.json"))
        if ctx and isinstance(ctx, dict):
            worktree = ctx.get("worktree", {})
            if isinstance(worktree, dict):
                abs_path = worktree.get("absPath", "").strip()
                if abs_path:
                    return abs_path

    # 3. .workflow/ 디렉터리 스캔
    try:
        registry = scan_active_workflows(project_root=project_root)
        if not registry:
            return None

        best_entry = None
        best_updated = ""
        for _key, entry in registry.items():
            work_dir = entry.get("workDir", "")
            abs_wd = (
                os.path.join(project_root, work_dir)
                if not os.path.isabs(work_dir)
                else work_dir
            )
            status = load_json_file(os.path.join(abs_wd, "status.json"))
            updated_at = status.get("updated_at", "") if isinstance(status, dict) else ""
            if updated_at >= best_updated:
                best_updated = updated_at
                best_entry = entry

        if best_entry:
            work_dir = best_entry.get("workDir", "")
            abs_wd = (
                os.path.join(project_root, work_dir)
                if not os.path.isabs(work_dir)
                else work_dir
            )
            ctx = load_json_file(os.path.join(abs_wd, ".context.json"))
            if ctx and isinstance(ctx, dict):
                worktree = ctx.get("worktree", {})
                if isinstance(worktree, dict):
                    abs_path = worktree.get("absPath", "").strip()
                    if abs_path:
                        return abs_path
    except Exception:
        pass

    return None


def _is_always_allowed_path(file_path: str) -> bool:
    """파일 경로가 항상 허용되는 경로인지 확인한다.

    .claude.workflow/ 하위 경로는 항상 허용된다.

    Args:
        file_path: 검사할 파일 경로

    Returns:
        항상 허용 경로이면 True.
    """
    for pattern in _ALWAYS_ALLOWED_PATTERNS:
        if pattern.search(file_path):
            return True
    return False


def _is_under_worktree(file_path: str, worktree_path: str) -> bool:
    """파일 경로가 워크트리 경로 하위인지 확인한다.

    Args:
        file_path: 검사할 파일 경로 (절대 또는 상대)
        worktree_path: 워크트리 절대경로

    Returns:
        워크트리 하위 경로이면 True.
    """
    # 절대 경로 정규화
    norm_worktree = os.path.normpath(worktree_path)
    # file_path가 절대 경로인 경우
    if os.path.isabs(file_path):
        norm_file = os.path.normpath(file_path)
        return norm_file.startswith(norm_worktree + os.sep) or norm_file == norm_worktree
    return False


def _get_suggested_path(file_path: str, project_root: str, worktree_path: str) -> str:
    """메인 리포 경로를 워크트리 내 경로로 변환하여 반환한다.

    Args:
        file_path: 원본 파일 경로
        project_root: 메인 리포 절대경로
        worktree_path: 워크트리 절대경로

    Returns:
        워크트리 내 경로 문자열.
    """
    norm_project = os.path.normpath(project_root)
    norm_file = os.path.normpath(file_path) if os.path.isabs(file_path) else file_path

    if os.path.isabs(norm_file) and norm_file.startswith(norm_project + os.sep):
        rel = norm_file[len(norm_project) + 1:]
        return os.path.join(worktree_path, rel)

    # 상대 경로인 경우 워크트리 경로에 직접 결합
    return os.path.join(worktree_path, file_path.lstrip("/"))


def _strip_quoted_args(command: str) -> str:
    """명령 문자열에서 따옴표로 감싼 영역의 내용을 빈 문자열로 치환한다.

    Args:
        command: Bash 도구의 원본 command 문자열

    Returns:
        따옴표 내부 내용이 제거된 문자열.
    """
    command = re.sub(r'"(?:[^"\\]|\\.)*"', '""', command)
    command = re.sub(r"'(?:[^'\\]|\\.)*'", "''", command)
    return command


def _extract_command_positions(command: str) -> list[str]:
    """명령 문자열을 파이프/체인 구분자로 분할하여 세그먼트 목록을 반환한다.

    Args:
        command: 따옴표 strip이 완료된 명령 문자열

    Returns:
        각 세그먼트의 선행 공백이 제거된 문자열 목록.
    """
    parts = re.split(r'&&|\|\||(?<!\|)\|(?!\|)|;', command)
    return [part.lstrip() for part in parts if part.strip()]


def _is_bash_file_modify(command: str) -> bool:
    """Bash 명령에서 파일 수정 패턴 포함 여부를 검사한다.

    따옴표로 감싼 인자 영역을 먼저 제거한 뒤,
    파이프/체인 구분자로 세그먼트를 분할하여
    각 세그먼트에서 _BASH_FILE_MODIFY_PATTERNS 패턴을 검사한다.

    Args:
        command: Bash 도구의 command 문자열

    Returns:
        파일 수정 패턴이 매칭되면 True, 아니면 False.
    """
    stripped = _strip_quoted_args(command)
    segments = _extract_command_positions(stripped)
    for segment in segments:
        for pattern in _BASH_FILE_MODIFY_PATTERNS:
            if re.search(pattern, segment):
                return True
    return False


def _bash_targets_main_repo(command: str, project_root: str, worktree_path: str) -> bool:
    """Bash 명령이 메인 리포 경로를 대상으로 파일 수정을 시도하는지 확인한다.

    명령에 메인 리포 절대경로가 포함되어 있고,
    워크트리 경로 내의 작업이 아닌 경우 메인 리포 타겟으로 판단한다.

    Args:
        command: Bash 도구의 command 문자열
        project_root: 메인 리포 절대경로
        worktree_path: 워크트리 절대경로

    Returns:
        메인 리포 경로를 타겟으로 하는 수정이면 True.
    """
    norm_project = os.path.normpath(project_root)
    norm_worktree = os.path.normpath(worktree_path)

    # 명령에 메인 리포 절대경로가 포함되는지 확인
    if norm_project not in command:
        return False

    # 명령에 워크트리 경로가 포함되어 있으면 워크트리 내 작업으로 허용
    # (메인 리포 경로가 포함되더라도 워크트리 경로 하위인 경우 통과)
    if norm_worktree in command:
        # 세분화: 메인 리포 경로가 워크트리 경로 바깥으로도 사용되는지 확인
        # 워크트리가 메인 리포 하위에 있으므로, 워크트리 경로가 있으면 허용
        return False

    return True


def main() -> None:
    """워크트리 경로 격리 가드 Hook의 진입점.

    stdin에서 JSON을 읽어 Write/Edit/Bash 도구 사용 시
    현재 세션이 워크플로우 implement 세션이고 워크트리가 설정된 경우,
    메인 리포 경로 파일 수정을 차단하고 워크트리 경로를 안내한다.

    비tmux 환경, 메인 세션, research/review 세션, 워크트리 없는 세션에서는 통과한다.
    .claude.workflow/ 하위 파일 Write/Edit는 항상 허용한다.
    """
    # .claude.workflow/.settings에서 설정 로드
    hook_flag = os.environ.get("HOOK_WORKTREE_PATH_GUARD") or read_env("HOOK_WORKTREE_PATH_GUARD")

    # Hook disable check (false/0 = disabled)
    if hook_flag in ("false", "0"):
        sys.exit(0)

    # stdin에서 JSON 읽기
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    tool_name = data.get("tool_name", "")

    # Write, Edit, Bash가 아니면 통과
    if tool_name not in ("Write", "Edit", "Bash"):
        sys.exit(0)

    # 세션 유형 확인 -- 워크플로우 세션이 아니면 통과 (이 가드의 관심사 아님)
    session_type = get_session_type()
    if session_type != "workflow":
        sys.exit(0)

    # --- 워크플로우 세션 확인됨, command 판별 ---

    command = _get_workflow_command()

    # command 조회 실패 시 통과 (false positive 방지)
    if command is None:
        sys.exit(0)

    # command 첫 세그먼트 추출 (체인 command 지원: "research>implement" -> "research")
    first_segment = command.split(">")[0].strip()

    # implement command가 아니면 통과 (research/review는 readonly_session_guard가 담당)
    if first_segment != _IMPLEMENT_COMMAND:
        sys.exit(0)

    # --- implement command 확인됨, 워크트리 경로 조회 ---

    worktree_path = _get_worktree_path()

    # 워크트리 경로가 없으면 통과 (비워크트리 implement 세션)
    if not worktree_path:
        sys.exit(0)

    # --- 워크트리 경로 확인됨, 파일 경로 검사 ---

    project_root = resolve_project_root()
    tool_input = data.get("tool_input", {})

    if tool_name in ("Write", "Edit"):
        file_path = tool_input.get("file_path", "")
        if not file_path:
            sys.exit(0)

        # 항상 허용 경로(.claude.workflow/)는 통과
        if _is_always_allowed_path(file_path):
            sys.exit(0)

        # 워크트리 하위 경로이면 통과
        if _is_under_worktree(file_path, worktree_path):
            sys.exit(0)

        # 상대 경로인 경우: 메인 리포 루트 기준 상대 경로는 통과 불가
        # (Claude Code가 메인 리포 루트를 cwd로 사용하므로 상대 경로 = 메인 리포 경로)
        suggested_path = _get_suggested_path(file_path, project_root, worktree_path)
        _deny(
            WORKTREE_PATH_WRITE_EDIT_DENIED.format(
                worktree_path=worktree_path,
                file_path=file_path,
                suggested_path=suggested_path,
            )
        )

    if tool_name == "Bash":
        bash_cmd = tool_input.get("command", "")
        if not bash_cmd:
            sys.exit(0)

        # 파일 수정 패턴이 없으면 통과
        if not _is_bash_file_modify(bash_cmd):
            sys.exit(0)

        # 메인 리포 절대경로를 대상으로 하는 수정이면 차단
        if _bash_targets_main_repo(bash_cmd, project_root, worktree_path):
            _deny(
                WORKTREE_PATH_BASH_MODIFY_DENIED.format(
                    worktree_path=worktree_path,
                )
            )
        sys.exit(0)

    # 알 수 없는 도구: 통과
    sys.exit(0)


if __name__ == "__main__":
    main()
