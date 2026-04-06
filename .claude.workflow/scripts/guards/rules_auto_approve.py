#!/usr/bin/env -S python3 -u
r"""`.claude/rules/` 경로 자동 승인 가드 Hook 스크립트.

PreToolUse(Write|Edit) 이벤트에서 `.claude/rules/` 하위 파일 대상 요청을 감지하여
`permissionDecision: allow`를 즉시 반환한다.

배경:
    Claude Code는 `.claude/` 디렉터리를 민감 파일로 분류하여 Write/Edit 시
    사용자 승인 프롬프트를 표시한다. `.claude/rules/` 는 워크플로우 규칙 파일이므로
    워커 에이전트가 자유롭게 수정할 수 있어야 한다.

주요 함수:
    main: Hook 진입점, stdin JSON 파싱 후 조건 충족 시 allow 반환

입력: stdin으로 JSON (tool_name, tool_input)
출력: 조건 충족 시 permissionDecision: allow JSON, 미충족 시 빈 출력

보안 제약:
    - `.claude/rules/` 하위만 승인 (정규식: r'\.claude/rules/')
    - `.claude/settings.json`, `.claude/settings.local.json` 등 다른 민감 경로는 승인하지 않음
    - `.claude/skills/`, `.claude/commands/`, `.claude/agents/` 등 다른 `.claude/` 경로도 승인하지 않음

토글:
    환경변수 HOOK_RULES_AUTO_APPROVE=false 설정 시 이 가드를 비활성화한다.
    비활성화 시 기존 Claude Code의 기본 승인 프롬프트 동작이 유지된다.
"""

from __future__ import annotations

import json
import os
import sys

# utils 패키지 import 경로 설정
_scripts_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from common import read_env

# `.claude/rules/` 하위만 허용하는 경로 키워드
_RULES_PATH_KEYWORD = ".claude/rules/"


def _allow(reason: str) -> None:
    """자동 승인 JSON을 stdout에 출력하고 프로세스를 종료한다.

    Args:
        reason: 승인 사유 문자열
    """
    result = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "permissionDecisionReason": reason,
        }
    }
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0)


def main() -> None:
    """`rules/` 경로 자동 승인 가드 Hook의 진입점.

    stdin에서 JSON을 읽어 Write/Edit 도구가 `.claude/rules/` 하위 파일을
    대상으로 할 때 즉시 allow를 반환한다.
    HOOK_RULES_AUTO_APPROVE=false 설정 시 비활성화된다.
    """
    # .claude.workflow/.settings(.env 폴백)에서 설정 로드
    hook_flag = os.environ.get("HOOK_RULES_AUTO_APPROVE") or read_env("HOOK_RULES_AUTO_APPROVE")

    # Hook disable check (false = disabled)
    if hook_flag in ("false", "0"):
        sys.exit(0)

    # stdin에서 JSON 읽기
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    tool_name = data.get("tool_name", "")

    # Write, Edit이 아니면 통과
    if tool_name not in ("Write", "Edit"):
        sys.exit(0)

    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    if not file_path:
        sys.exit(0)

    # `.claude/rules/` 하위 경로인지 확인
    # 보안: 정확히 `.claude/rules/` 하위만 허용, 다른 `.claude/` 경로는 불허
    if _RULES_PATH_KEYWORD in file_path:
        _allow("auto-approve .claude/rules/ path")

    # 조건 미충족 시 빈 출력으로 통과 (기존 동작 유지)
    sys.exit(0)


if __name__ == "__main__":
    main()
