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

# utils 패키지 import 경로 설정
_scripts_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from common import read_env

# flow-kanban 유효 서브커맨드 집합
VALID_SUBCOMMANDS: frozenset[str] = frozenset({
    "create",
    "move",
    "done",
    "delete",
    "add-subnumber",
    "update-title",
    "update-subnumber",
    "archive-subnumber",
})

# flow-kanban 명령 감지 및 서브커맨드 추출 패턴
# flow-kanban 뒤의 첫 번째 인자를 서브커맨드로 파싱
_FLOW_KANBAN_PATTERN = re.compile(r"\bflow-kanban\s+([a-zA-Z][\w-]*)")


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
    # .claude.env에서 설정 로드
    hook_flag = os.environ.get("HOOK_KANBAN_SUBCOMMAND_GUARD") or read_env("HOOK_KANBAN_SUBCOMMAND_GUARD")

    # Hook disable check (false = disabled)
    if hook_flag in ("false", "0"):
        sys.exit(0)

    # stdin에서 JSON 읽기
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    tool_name = data.get("tool_name", "")

    # Bash가 아니면 통과
    if tool_name != "Bash":
        sys.exit(0)

    tool_input = data.get("tool_input", {})
    command = tool_input.get("command", "")
    if not command:
        sys.exit(0)

    # flow-kanban 명령이 포함되어 있지 않으면 통과
    if "flow-kanban" not in command:
        sys.exit(0)

    # 서브커맨드 추출
    match = _FLOW_KANBAN_PATTERN.search(command)
    if not match:
        # flow-kanban만 있고 서브커맨드가 없는 경우 (도움말 등) 통과
        sys.exit(0)

    subcommand = match.group(1)

    # 유효 서브커맨드 검사
    if subcommand in VALID_SUBCOMMANDS:
        sys.exit(0)

    # 유효하지 않은 서브커맨드 차단
    valid_list = ", ".join(sorted(VALID_SUBCOMMANDS))
    _deny(
        f"flow-kanban의 유효하지 않은 서브커맨드 '{subcommand}'가 차단되었습니다. "
        f"유효한 서브커맨드: {valid_list}"
    )


if __name__ == "__main__":
    main()
