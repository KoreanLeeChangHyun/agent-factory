#!/usr/bin/env -S python3 -u
"""
위험한 명령어 차단 Hook 스크립트

PreToolUse(Bash) 이벤트에서 위험 명령어 패턴 매칭 후 차단.

입력: stdin으로 JSON (tool_name, tool_input)
출력: 차단 시 hookSpecificOutput JSON, 통과 시 빈 출력
"""

import json
import os
import re
import sys

# utils 패키지 import 경로 설정
_scripts_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from utils.env_utils import read_env


def _deny(blocked, alternative):
    """차단 JSON을 출력하고 종료."""
    reason = f"위험한 명령어가 감지되었습니다: {blocked}. 안전한 대안: {alternative}"
    result = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0)


def _load_patterns():
    """data/danger_patterns.json에서 패턴을 로드.

    보안 우선: 로드 실패 시 모든 명령을 차단하는 폴백 패턴 반환.

    Returns:
        tuple: (whitelist_patterns, danger_patterns)
            whitelist_patterns: [(pattern, None), ...]
            danger_patterns: [(pattern, blocked, alternative), ...]
    """
    data_file = os.path.join(_scripts_dir, "data", "danger_patterns.json")
    try:
        with open(data_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        whitelist = [(item["pattern"], None) for item in data.get("whitelist", [])]
        danger = [
            (item["pattern"], item["blocked"], item["alternative"])
            for item in data.get("danger", [])
        ]
        return whitelist, danger
    except (json.JSONDecodeError, IOError, OSError, KeyError, TypeError):
        # 보안 우선: 로드 실패 시 빈 화이트리스트 + 전체 차단 폴백
        print(
            f"[dangerous_command_guard] CRITICAL: danger_patterns.json 로드 실패 - 보안 폴백 적용",
            file=sys.stderr,
        )
        return [], [
            (
                r".",
                "위험 패턴 데이터 로드 실패 (보안 폴백)",
                "시스템 관리자에게 data/danger_patterns.json 파일 상태를 확인 요청하세요.",
            )
        ]


# 모듈 레벨에서 한 번만 로드
WHITELIST_PATTERNS, DANGER_PATTERNS = _load_patterns()


def main():
    # .claude.env에서 설정 로드
    hook_flag = os.environ.get("HOOK_DANGEROUS_COMMAND") or read_env("HOOK_DANGEROUS_COMMAND")

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

    # 화이트리스트 검사 (안전한 패턴은 통과)
    for wl_pattern, _ in WHITELIST_PATTERNS:
        if re.search(wl_pattern, command):
            sys.exit(0)

    # 위험 패턴 검사
    for pattern, blocked, alternative in DANGER_PATTERNS:
        if re.search(pattern, command):
            _deny(blocked, alternative)

    # 위험 패턴 미매칭 시 통과
    sys.exit(0)


if __name__ == "__main__":
    main()
