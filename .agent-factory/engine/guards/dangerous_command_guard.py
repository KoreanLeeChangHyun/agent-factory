#!/usr/bin/env -S python3 -u
"""위험한 명령어 차단 Hook 스크립트.

PreToolUse(Bash) 이벤트에서 위험 명령어 패턴 매칭 후 차단.

주요 함수:
    main: Hook 진입점, stdin JSON 파싱 후 위험 명령어 차단

입력: stdin으로 JSON (tool_name, tool_input)
출력: 차단 시 hookSpecificOutput JSON, 통과 시 빈 출력
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

from common import read_env

# Loading dangerous command patterns (Security priority: full blocking fallback in case of import failure)
try:
    from constants import DANGER_WHITELIST, DANGER_PATTERNS
    WHITELIST_PATTERNS: list[tuple[str, None]] = [(item["pattern"], None) for item in DANGER_WHITELIST]
    DANGER_PATTERN_LIST: list[tuple[str, str, str]] = [
        (item["pattern"], item["blocked"], item["alternative"])
        for item in DANGER_PATTERNS
    ]
except ImportError:
    print(
        "[dangerous_command_guard] CRITICAL: data.constants import failed - apply security fallback",
        file=sys.stderr,
    )
    WHITELIST_PATTERNS = []
    DANGER_PATTERN_LIST = [
        (
            r".",
            "Risk pattern data load failure (security fallback)",
            "Ask your system administrator to check the status of the data/constants.py file.",
        )
    ]


def _deny(blocked: str, alternative: str) -> None:
    """차단 JSON을 stdout에 출력하고 프로세스를 종료한다.

    Args:
        blocked: 차단된 명령어 또는 패턴 설명
        alternative: 안전한 대안 안내 문자열
    """
    reason = f"Dangerous command detected: {blocked}. Safe alternative: {alternative}"
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
    """위험한 명령어 차단 Hook의 진입점.

    stdin에서 JSON을 읽어 Bash 도구 실행 시 위험 패턴을 검사하고,
    매칭 시 deny 응답을 출력하여 실행을 차단한다.
    화이트리스트 패턴에 매칭되면 검사를 건너뛴다.
    """
    # Load settings from .agent-factory/.settings
    hook_flag = os.environ.get("HOOK_DANGEROUS_COMMAND") or read_env("HOOK_DANGEROUS_COMMAND")

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

    # Whitelist check (safe patterns pass)
    for wl_pattern, _ in WHITELIST_PATTERNS:
        if re.search(wl_pattern, command):
            sys.exit(0)

    # Risk pattern inspection
    for pattern, blocked, alternative in DANGER_PATTERN_LIST:
        if re.search(pattern, command):
            _deny(blocked, alternative)

    # Passes when risk pattern does not match
    sys.exit(0)


if __name__ == "__main__":
    main()
