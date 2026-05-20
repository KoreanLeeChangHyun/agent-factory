#!/usr/bin/env -S python3 -u
"""직접 경로 호출 차단 가드 Hook 스크립트.

PreToolUse(Bash) 이벤트에서 python3 .agent-factory/engine/ 패턴의 직접 경로 호출을
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

# Set utils package import path
_engine_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _engine_dir not in sys.path:
    sys.path.insert(0, _engine_dir)

# Guard message module import path setting
_guards_dir = os.path.dirname(os.path.abspath(__file__))
if _guards_dir not in sys.path:
    sys.path.insert(0, _guards_dir)

from common import read_env
from messages import DIRECT_PATH_CALL_DENIED

# Direct path call detection pattern (detection of both relative and absolute paths)
_DIRECT_PATH_PATTERN = re.compile(
    r"python3(?:\s+-u)?\s+(?:\$CLAUDE_PROJECT_DIR/)?"
    r"(?:\.agent-factory/engine/|/[^\s]*\.agent-factory/engine/)"
)

# Allowed exception patterns (fixed calling routes in settings.json hooks/statusLine, etc.)
_ALLOWED_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"python3(?:\s+-u)?\s+(?:\$CLAUDE_PROJECT_DIR/)?(?:\.agent-factory/|/[^\s]*\.agent-factory/)hooks/"),
    re.compile(r"python3(?:\s+-u)?\s+(?:\$CLAUDE_PROJECT_DIR/)?(?:\.agent-factory/|/[^\s]*\.agent-factory/)engine/(?:apps/hooks/)?statusline\.py"),
    re.compile(r"python3(?:\s+-u)?\s+(?:\$CLAUDE_PROJECT_DIR/)?(?:\.agent-factory/|/[^\s]*\.agent-factory/)board/server\.py"),
    re.compile(r"python3(?:\s+-u)?\s+(?:\$CLAUDE_PROJECT_DIR/)?(?:\.agent-factory/|/[^\s]*\.agent-factory/)engine/(?:apps/cli/)?claude_edit\.py"),
]

# Pattern allowing history_sync.py calls following the hook dispatcher in && chains
# Example (relative path): python3 .agent-factory/hooks/... && python3 .agent-factory/engine/adapters/sync/history_sync.py ...
# Example (absolute path): python3 /path/.agent-factory/hooks/... && python3 /path/.agent-factory/engine/adapters/sync/history_sync.py ...
_CHAINED_HISTORY_SYNC_PATTERN = re.compile(
    r"python3(?:\s+-u)?\s+(?:\$CLAUDE_PROJECT_DIR/)?"
    r"(?:\.agent-factory/|/[^\s]*\.agent-factory/)hooks/\S*\s*&&\s*"
    r"python3(?:\s+-u)?\s+(?:\$CLAUDE_PROJECT_DIR/)?"
    r"(?:\.agent-factory/engine/(?:adapters/)?sync/|/[^\s]*\.agent-factory/engine/(?:adapters/)?sync/)history_sync\.py"
)

# Script file name -> alias mapping
ALIAS_MAP: dict[str, str] = {
    "update_state.py": "flow-update",
    "skill_mapper.py": "flow-skillmap",
    "state.py": "flow-skill",
    "skill_state_manager.py": "flow-skill",
    "plan_validator.py": "flow-validate",
    "prompt_validator.py": "flow-validate-p",
    "garbage_collect.py": "flow-gc",
    "kanban.py": "flow-kanban",
    "merge_pipeline.py": "flow-merge",
    "history_sync.py": "flow-history",
    "catalog_sync.py": "flow-catalog",
    "git_config.py": "flow-gitconfig",
    "project_detector.py": "flow-detect",
    "project_skill_detector.py": "flow-detect",
    "migrate_runs_fold.py": "flow-migrate-runs",
}

# Pattern to extract only the file name from the script file name (both relative and absolute paths supported)
_SCRIPT_NAME_PATTERN = re.compile(
    r"python3(?:\s+-u)?\s+(?:\$CLAUDE_PROJECT_DIR/)?"
    r"(?:\.agent-factory/engine/|/[^\s]*\.agent-factory/engine/)(?:\S+/)?(\S+\.py)"
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


def _extract_script_name(command: str) -> str | None:
    """명령어에서 .agent-factory/engine/ 하위 스크립트 파일명을 추출한다.

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
    # Allowed exception pattern check
    for pattern in _ALLOWED_PATTERNS:
        if pattern.search(command):
            return True

    # Allow history_sync.py call after hook dispatcher in && chain
    if _CHAINED_HISTORY_SYNC_PATTERN.search(command):
        return True

    return False


def main() -> None:
    """직접 경로 호출 차단 가드 Hook의 진입점.

    stdin에서 JSON을 읽어 Bash 도구의 python3 .agent-factory/engine/ 직접 호출을 감지하고,
    flow-* alias 사용을 안내하는 deny 응답을 출력하여 차단한다.
    settings.json에서 고정 호출하는 경로는 예외로 허용한다.
    """
    # Load settings from .agent-factory/.settings
    hook_flag = os.environ.get("HOOK_DIRECT_PATH_GUARD") or read_env("HOOK_DIRECT_PATH_GUARD")

    # Hook disable check (not set or false = disabled)
    if not hook_flag or hook_flag in ("false", "0"):
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

    # Pass if there is no direct route call pattern
    if not _DIRECT_PATH_PATTERN.search(command):
        sys.exit(0)

    # Allow exception check
    if _is_allowed(command):
        sys.exit(0)

    # Script file name extraction and alias mapping
    script_name = _extract_script_name(command)
    if script_name and script_name in ALIAS_MAP:
        alias_name = ALIAS_MAP[script_name]
        _deny(DIRECT_PATH_CALL_DENIED.format(
            script_name=script_name,
            alias_name=alias_name,
        ))
    elif script_name:
        # Scripts not in ALIAS_MAP (hook only, etc.) - General blocking message
        _deny(DIRECT_PATH_CALL_DENIED.format(
            script_name=script_name,
            alias_name="(No applicable alias - may be a hook/internal-only script)",
        ))
    else:
        # General blocking when script name extraction fails
        _deny(DIRECT_PATH_CALL_DENIED.format(
            script_name=".agent-factory/engine/...",
            alias_name="flow-*",
        ))


if __name__ == "__main__":
    main()
