#!/usr/bin/env -S python3 -u
"""flow-kanban 서브커맨드 유효성 검증 가드 Hook 스크립트.

PreToolUse(Bash) 이벤트에서 flow-kanban 명령의 서브커맨드를 파싱하여
유효하지 않은 서브커맨드 사용을 차단한다.

주요 함수:
    main: Hook 진입점, stdin JSON 파싱 후 유효하지 않은 서브커맨드 차단

입력: stdin으로 JSON (tool_name, tool_input)
출력: 차단 시 hookSpecificOutput JSON, 통과 시 빈 출력

토글: 환경변수 HOOK_KANBAN_SUBCOMMAND_GUARD (false/0 = 비활성, 기본 활성)
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

from common import read_env
from messages import KANBAN_INVALID_SUBCOMMAND, KANBAN_SUBMIT_REMOVED

# flow-kanban valid subcommand set
VALID_SUBCOMMANDS: frozenset[str] = frozenset({
    "create",
    "move",
    "done",
    "delete",
    "update-title",
    "update",
    "update-prompt",
    "update-result",
    "link",
    "unlink",
    "list",   # Ticket list inquiry
    "board",  # Check overall Kanban board status
    "show",   # View specific ticket details
})

# flow-kanban command detection and subcommand extraction pattern
# Parse the first argument after flow-kanban as a subcommand
_FLOW_KANBAN_PATTERN = re.compile(r"\bflow-kanban\s+([a-zA-Z][\w-]*)")

# The Submit transient step has been removed, so submit cannot be used as the target argument of move.
_FLOW_KANBAN_MOVE_SUBMIT_PATTERN = re.compile(r"\bflow-kanban\s+move\s+T-\d+\s+submit\b")


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


def main() -> None:
    """flow-kanban 서브커맨드 유효성 검증 Hook의 진입점.

    stdin에서 JSON을 읽어 Bash 도구의 flow-kanban 명령을 감지하고,
    서브커맨드가 유효 집합에 없으면 deny 응답을 출력하여 차단한다.
    """
    # Load settings from .agent-factory/.settings
    hook_flag = os.environ.get("HOOK_KANBAN_SUBCOMMAND_GUARD") or read_env("HOOK_KANBAN_SUBCOMMAND_GUARD")

    # Hook disable check (false = disabled)
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

    # Pass if flow-kanban command is not included
    if "flow-kanban" not in command:
        sys.exit(0)

    # Subcommand extraction
    match = _FLOW_KANBAN_PATTERN.search(command)
    if not match:
        # Passes if there is only flow-kanban and no subcommands (help, etc.)
        sys.exit(0)

    subcommand = match.group(1)

    # Valid subcommand check
    if subcommand in VALID_SUBCOMMANDS:
        if subcommand == "move" and _FLOW_KANBAN_MOVE_SUBMIT_PATTERN.search(command):
            _deny(KANBAN_SUBMIT_REMOVED)
        sys.exit(0)

    # Blocking invalid subcommands
    valid_list = ", ".join(sorted(VALID_SUBCOMMANDS))
    _deny(KANBAN_INVALID_SUBCOMMAND.format(subcommand=subcommand, valid_list=valid_list))


if __name__ == "__main__":
    main()
