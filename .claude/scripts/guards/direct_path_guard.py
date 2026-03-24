#!/usr/bin/env -S python3 -u
"""직접 경로 호출 차단 가드 Hook 스크립트.

PreToolUse(Bash) 이벤트에서 python3 .claude/scripts/ 패턴의 직접 경로 호출을
감지하여 flow-* alias 사용을 안내하는 가드 스크립트.

주요 함수:
    main: Hook 진입점, stdin JSON 파싱 후 직접 경로 호출 차단

입력: stdin으로 JSON (tool_name, tool_input)
출력: 차단 시 hookSpecificOutput JSON, 통과 시 빈 출력

토글: 환경변수 HOOK_DIRECT_PATH_GUARD (false/0 = 비활성, 기본 활성)
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

from common import read_env
from messages import DIRECT_PATH_CALL_DENIED

# 직접 경로 호출 감지 패턴
_DIRECT_PATH_PATTERN = re.compile(r"python3\s+\.claude/scripts/")

# 허용 예외 패턴 (settings.json hooks/statusLine 등에서 고정 호출하는 경로)
_ALLOWED_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"python3\s+\.claude/hooks/"),              # hook 디스패처 호출
    re.compile(r"python3\s+\.claude/scripts/statusline\.py"),  # statusLine command
    re.compile(r"python3\s+\.claude/board/server\.py"),    # SessionStart board server
]

# && 체인에서 hook 디스패처 뒤에 이어지는 history_sync.py 호출 허용 패턴
# 예: python3 .claude/hooks/... && python3 .claude/scripts/sync/history_sync.py ...
_CHAINED_HISTORY_SYNC_PATTERN = re.compile(
    r"python3\s+\.claude/hooks/\S+\s*&&\s*python3\s+\.claude/scripts/sync/history_sync\.py"
)

# 스크립트 파일명 -> alias 매핑
ALIAS_MAP: dict[str, str] = {
    "initialization.py": "flow-init",
    "finalization.py": "flow-finish",
    "reload_prompt.py": "flow-reload",
    "update_state.py": "flow-update",
    "skill_mapper.py": "flow-skillmap",
    "skill_state_manager.py": "flow-skill",
    "plan_validator.py": "flow-validate",
    "prompt_validator.py": "flow-validate-p",
    "skill_recommender.py": "flow-recommend",
    "garbage_collect.py": "flow-gc",
    "kanban.py": "flow-kanban",
    "merge_pipeline.py": "flow-merge",
    "tmux_launcher.py": "flow-tmux",
    "history_sync.py": "flow-history",
    "catalog_sync.py": "flow-catalog",
    "git_config.py": "flow-gitconfig",
    "project_skill_detector.py": "flow-detect",
}

# 스크립트 파일명에서 파일명만 추출하는 패턴
_SCRIPT_NAME_PATTERN = re.compile(r"python3\s+\.claude/scripts/(?:\S+/)?(\S+\.py)")


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


def _extract_script_name(command: str) -> str | None:
    """명령어에서 .claude/scripts/ 하위 스크립트 파일명을 추출한다.

    Args:
        command: Bash 명령어 문자열

    Returns:
        스크립트 파일명 (예: "kanban.py") 또는 None
    """
    match = _SCRIPT_NAME_PATTERN.search(command)
    if match:
        return match.group(1)
    return None


def _is_allowed(command: str) -> bool:
    """명령어가 허용 예외 패턴에 해당하는지 확인한다.

    Args:
        command: Bash 명령어 문자열

    Returns:
        허용 예외이면 True, 차단 대상이면 False
    """
    # 허용 예외 패턴 검사
    for pattern in _ALLOWED_PATTERNS:
        if pattern.search(command):
            return True

    # && 체인에서 hook 디스패처 뒤 history_sync.py 호출 허용
    if _CHAINED_HISTORY_SYNC_PATTERN.search(command):
        return True

    return False


def main() -> None:
    """직접 경로 호출 차단 가드 Hook의 진입점.

    stdin에서 JSON을 읽어 Bash 도구의 python3 .claude/scripts/ 직접 호출을 감지하고,
    flow-* alias 사용을 안내하는 deny 응답을 출력하여 차단한다.
    settings.json에서 고정 호출하는 경로는 예외로 허용한다.
    """
    # .claude.env에서 설정 로드
    hook_flag = os.environ.get("HOOK_DIRECT_PATH_GUARD") or read_env("HOOK_DIRECT_PATH_GUARD")

    # Hook disable check (미설정 또는 false = disabled)
    if not hook_flag or hook_flag in ("false", "0"):
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

    # 직접 경로 호출 패턴이 없으면 통과
    if not _DIRECT_PATH_PATTERN.search(command):
        sys.exit(0)

    # 허용 예외 검사
    if _is_allowed(command):
        sys.exit(0)

    # 스크립트 파일명 추출 및 alias 매핑
    script_name = _extract_script_name(command)
    if script_name and script_name in ALIAS_MAP:
        alias_name = ALIAS_MAP[script_name]
        _deny(DIRECT_PATH_CALL_DENIED.format(
            script_name=script_name,
            alias_name=alias_name,
        ))
    elif script_name:
        # ALIAS_MAP에 없는 스크립트 (hook 전용 등) - 일반 차단 메시지
        _deny(DIRECT_PATH_CALL_DENIED.format(
            script_name=script_name,
            alias_name="(해당 alias 없음 - hook/내부 전용 스크립트일 수 있습니다)",
        ))
    else:
        # 스크립트명 추출 실패 시 일반 차단
        _deny(DIRECT_PATH_CALL_DENIED.format(
            script_name=".claude/scripts/...",
            alias_name="flow-*",
        ))


if __name__ == "__main__":
    main()
