#!/usr/bin/env -S python3 -u
"""워크트리 삭제 전 미커밋 변경 방어 가드 Hook 스크립트.

PreToolUse(Bash) 이벤트에서 ``git worktree remove`` 명령을 감지하고,
대상 워크트리에 미커밋 변경이 있으면 차단한다.

경로 추출에 실패하거나 대상 디렉터리가 존재하지 않으면 통과(false positive 방지).
미커밋 변경이 없으면 통과.

주요 함수:
    main: Hook 진입점, stdin JSON 파싱 후 워크트리 미커밋 변경 차단

입력: stdin으로 JSON (tool_name, tool_input)
출력: 차단 시 hookSpecificOutput JSON, 통과 시 빈 출력

토글: 환경변수 HOOK_WORKTREE_REMOVE_GUARD (false/0 = 비활성, 기본 활성)
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys

# Set utils package import path
_engine_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _engine_dir not in sys.path:
    sys.path.insert(0, _engine_dir)

from common import read_env
from flow.worktree_manager import has_uncommitted_changes

# ``git worktree remove [--force] <path>`` command pattern
_WORKTREE_REMOVE_PATTERN: str = r"\bgit\s+worktree\s+remove\b"


def _deny(worktree_path: str, status_output: str) -> None:
    """차단 JSON을 stdout에 출력하고 프로세스를 종료한다.

    Args:
        worktree_path: 미커밋 변경이 감지된 워크트리 경로.
        status_output: ``git status --porcelain`` 출력 (미커밋 파일 목록).
    """
    reason = (
        f"[Block worktree deletion] This is a worktree with uncommitted changes: {worktree_path} \n"
        f"List of uncommitted files: \n {status_output} \n"
        "Complete with the normal path using flow-merge."
    )
    result = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0)


def _extract_worktree_path(command: str) -> str | None:
    """``git worktree remove [--force] <path>`` 명령에서 경로 인자를 추출한다.

    ``--force`` 플래그를 건너뛰고 첫 번째 비옵션 인자를 경로로 반환한다.
    추출에 실패하거나 인자가 없으면 None을 반환한다.

    Args:
        command: Bash 도구의 command 문자열.

    Returns:
        워크트리 경로 문자열. 추출 실패 시 None.
    """
    # After ``git worktree remove``, only the arguments are parsed.
    match = re.search(_WORKTREE_REMOVE_PATTERN, command)
    if not match:
        return None

    # Extract remaining string after matching end position
    remainder = command[match.end():].strip()
    if not remainder:
        return None

    # Token separation (simple space-based separation; quoted paths are out of scope for processing)
    tokens = remainder.split()
    for token in tokens:
        # ``--force`` or ``-f`` flags are skipped
        if token in ("--force", "-f"):
            continue
        # Returns the first non-optional argument as a path
        return token

    return None


def _get_status_output(worktree_path: str) -> str:
    """워크트리 경로에서 ``git status --porcelain`` 출력을 반환한다.

    명령 실행에 실패하면 빈 문자열을 반환한다.

    Args:
        worktree_path: 검사할 워크트리 디렉터리 경로.

    Returns:
        ``git status --porcelain`` 표준 출력. 실패 시 빈 문자열.
    """
    try:
        result = subprocess.run(
            ["git", "-C", worktree_path, "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return ""


def main() -> None:
    """워크트리 삭제 전 미커밋 변경 방어 가드 Hook의 진입점.

    stdin에서 JSON을 읽어 Bash 도구의 ``git worktree remove`` 명령을 감지하고,
    대상 워크트리에 미커밋 변경이 있으면 deny 응답을 출력하여 삭제를 차단한다.

    경로 추출 실패, 디렉터리 부재, 미커밋 없음 시에는 통과한다.
    """
    # Load settings from .agent-factory/.settings
    hook_flag = os.environ.get("HOOK_WORKTREE_REMOVE_GUARD") or read_env("HOOK_WORKTREE_REMOVE_GUARD")

    # Hook disable check (false/0 = disabled)
    if hook_flag in ("false", "0"):
        sys.exit(0)

    # Reading JSON from stdin
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    tool_name = data.get("tool_name", "")

    # Pass if not Bash
    if tool_name != "Bash":
        sys.exit(0)

    tool_input = data.get("tool_input", {})
    command = tool_input.get("command", "")
    if not command:
        sys.exit(0)

    # Passes if ``git worktree remove`` pattern is not present
    if not re.search(_WORKTREE_REMOVE_PATTERN, command):
        sys.exit(0)

    # Extract worktree path from command (pass on failure — avoid false positives)
    worktree_path = _extract_worktree_path(command)
    if not worktree_path:
        sys.exit(0)

    # Pass if not a directory (already deleted path, etc.)
    if not os.path.isdir(worktree_path):
        sys.exit(0)

    # Check for uncommitted changes (if failed, return False → pass)
    if not has_uncommitted_changes(worktree_path):
        sys.exit(0)

    # There are uncommitted changes → Blocked
    status_output = _get_status_output(worktree_path)
    _deny(worktree_path, status_output)


if __name__ == "__main__":
    main()
