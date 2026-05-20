#!/usr/bin/env -S python3 -u
"""research/review 세션 Write/Edit/Bash 차단 가드 Hook 스크립트.

PreToolUse(Write|Edit|Bash) 이벤트에서 현재 세션이 워크플로우 세션이고
활성 워크플로우의 command가 research 또는 review이면 코드 수정을 차단한다.

주요 함수:
    main: Hook 진입점, stdin JSON 파싱 후 research/review 세션 Write/Edit/Bash 차단

입력: stdin으로 JSON (tool_name, tool_input)
출력: 차단 시 hookSpecificOutput JSON, 통과 시 빈 출력

토글: 환경변수 HOOK_READONLY_SESSION_GUARD (false/0 = 비활성, 기본 활성)
"""

from __future__ import annotations

import json
import os
import re
import sys

# Set utils package import path
_engine_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _engine_dir not in sys.path:
    sys.path.insert(0, _engine_dir)

# Guard message module import path setting
_guards_dir = os.path.dirname(os.path.abspath(__file__))
if _guards_dir not in sys.path:
    sys.path.insert(0, _guards_dir)

from common import load_json_file, read_env, resolve_project_root, scan_active_workflows
from flow.session_identifier import get_session_type
from messages import (
    READONLY_SESSION_BASH_MODIFY_DENIED,
    READONLY_SESSION_WRITE_EDIT_DENIED,
)

# Read-only command list (code modification is prohibited in these commands)
_READONLY_COMMANDS = ("research", "review")

# Command pattern that allows Bash tools to modify files (same as main_session_guard.py)
_BASH_FILE_MODIFY_PATTERNS: list[str] = [
    r"\bsed\s+-i",                               # sed inplace
    r"\bawk\s+.*-i\s+inplace",                   # awk inplace
    r"\b(echo|printf)\s+.*\s*>{1,2}\s*\S",       # echo/printf redirect
    r"\btee\s+(-a\s+)?\S",                       # write tee
    r"\bcat\s*<<",                               # heredoc redirect
    r"\bcp\s+",                                  # copy files
    r"\bmv\s+",                                  # move files
    r"\bpython3?\s+(-c\s+|.*\bopen\b.*\bwrite\b)",  # python -c open write
    r"\bperl\s+-.*[pi]",                         # perl inplace
    r"(?:^|[;&|]\s*)\binstall\s+",               # install command (excluding subcommands)
    r"\bdd\s+",                                  # dd command
]

# .agent-factory/ subpath pattern (allows Report/History Write/Edit)
_WORKFLOW_PATH_PATTERN = re.compile(r"[/\\]?\.claude\.workflow[/\\]")

# User memory directory pattern: ~/.claude/projects/<encoded>/memory/** matching
# Same policy as main_session_guard.py (allow memory writing in research/review sessions as well)
_MEMORY_DIR_PATTERN: re.Pattern[str] = re.compile(
    r"(?:^|/)\.claude/projects/[^/]+/memory(?:/|$)"
)


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

    # 1. Check the WORKFLOW_WORK_DIR environment variable
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

    # 2. Scan the .workflow/ directory
    try:
        registry = scan_active_workflows(project_root=project_root)
        if not registry:
            return None

        # Select the most recent workflow by updated_at
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


def _is_workflow_path(file_path: str) -> bool:
    """파일 경로가 .workflow/ 하위인지 확인한다.

    Args:
        file_path: 검사할 파일 경로

    Returns:
        .workflow/ 하위 경로이면 True.
    """
    return bool(_WORKFLOW_PATH_PATTERN.search(file_path))


def _is_memory_path(path: str) -> bool:
    """파일 경로가 사용자 메모리 디렉터리 하위인지 확인한다.

    ~/.claude/projects/<encoded>/memory/ 또는 그 하위 경로를 매칭한다.
    main_session_guard.py와 동일한 로직.

    Args:
        path: 검사할 파일 경로 (절대경로 또는 ~ 시작 경로)

    Returns:
        메모리 디렉터리 하위 경로이면 True, 아니면 False.
    """
    if not path:
        return False
    expanded = os.path.expanduser(path)
    return bool(_MEMORY_DIR_PATTERN.search(expanded))


def main() -> None:
    """research/review 세션 Write/Edit/Bash 차단 Hook의 진입점.

    stdin에서 JSON을 읽어 Write/Edit/Bash 도구 사용 시 현재 세션이
    워크플로우 세션이고 command가 research/review이면
    deny 응답을 출력하여 코드 수정을 차단한다.

    비워크플로우 세션에서는 무조건 통과한다.
    .workflow/ 하위 파일 Write/Edit는 허용한다.
    """
    # Load settings from .agent-factory/.settings
    hook_flag = os.environ.get("HOOK_READONLY_SESSION_GUARD") or read_env("HOOK_READONLY_SESSION_GUARD")

    # Hook disable check (false/0 = disabled)
    if hook_flag in ("false", "0"):
        sys.exit(0)

    # Reading JSON from stdin
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    tool_name = data.get("tool_name", "")

    # Pass if not Write, Edit, or Bash
    if tool_name not in ("Write", "Edit", "Bash"):
        sys.exit(0)

    # Determine session type -- pass if not a workflow session (not a concern of this guard)
    session_type = get_session_type()
    if session_type != "workflow":
        sys.exit(0)

    # --- Workflow session confirmed, command determination ---

    command = _get_workflow_command()

    # Passes when command inquiry fails (prevents false positives)
    if command is None:
        sys.exit(0)

    # Extract the first segment of the command (support chain command: "research>implement" -> "research")
    first_segment = command.split(">")[0].strip()

    # Passes if implement command
    if first_segment not in _READONLY_COMMANDS:
        sys.exit(0)

    # --- research/review command confirmed, blocking determined ---

    tool_input = data.get("tool_input", {})

    # Write/Edit tools: .workflow/ sub or memory directory sub is allowed
    if tool_name in ("Write", "Edit"):
        file_path = tool_input.get("file_path", "")
        if _is_workflow_path(file_path) or _is_memory_path(file_path):
            sys.exit(0)
        _deny(READONLY_SESSION_WRITE_EDIT_DENIED)

    # Bash tool: Block only file modification patterns
    if tool_name == "Bash":
        command_str = tool_input.get("command", "")
        if _is_bash_file_modify(command_str):
            _deny(READONLY_SESSION_BASH_MODIFY_DENIED)
        sys.exit(0)

    # Unknown tool: Passed
    sys.exit(0)


if __name__ == "__main__":
    main()
