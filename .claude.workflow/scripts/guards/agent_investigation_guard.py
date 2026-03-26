#!/usr/bin/env -S python3 -u
"""메인 세션 조사 목적 서브에이전트 차단 가드 Hook 스크립트.

PreToolUse(Task) 이벤트에서 subagent_type이 조사 목적(Explore, general-purpose)이거나
허용 목록에 없는 미지정값인 경우, 현재 tmux 윈도우가 워크플로우 세션
(P:T-* 접두사)이 아닌 메인 세션이면 해당 서브에이전트 호출을 차단한다.
비tmux 환경(TMUX_PANE 미설정)에서도 차단한다.

허용 subagent_type: worker-opus, worker-sonnet, planner, reporter, validator

주요 함수:
    main: Hook 진입점, stdin JSON 파싱 후 조사 목적 서브에이전트 차단

입력: stdin으로 JSON (tool_name, tool_input)
출력: 차단 시 hookSpecificOutput JSON, 통과 시 빈 출력

토글: 환경변수 HOOK_AGENT_INVESTIGATION_GUARD (false/0 = 비활성, 기본 활성)
"""

from __future__ import annotations

import json
import os
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
from messages import (
    AGENT_INVESTIGATION_MAIN_SESSION_DENIED,
    AGENT_INVESTIGATION_WINDOW_QUERY_FAILED,
)

# 워크플로우 세션 윈도우명 접두사
_WORKFLOW_WINDOW_PREFIX = "P:T-"

# 허용된 subagent_type 목록 (워크플로우 전용 서브에이전트)
_ALLOWED_SUBAGENT_TYPES: frozenset[str] = frozenset({
    "worker-opus",
    "worker-sonnet",
    "planner",
    "reporter",
    "validator",
})


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


def _get_current_window_name() -> str | None:
    """현재 tmux 윈도우 이름을 반환한다.

    TMUX_PANE 환경변수가 없으면 None을 반환한다.
    tmux 명령 실행 실패 시에도 None을 반환한다.

    Returns:
        현재 윈도우명 문자열. 비tmux 환경 또는 실행 실패 시 None.
    """
    import subprocess

    tmux_pane = os.environ.get("TMUX_PANE")
    if not tmux_pane:
        return None

    try:
        result = subprocess.run(
            ["tmux", "display-message", "-t", tmux_pane, "-p", "#W"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return None


def _extract_subagent_type(tool_input: dict) -> str:
    """tool_input에서 subagent_type을 추출한다.

    tool_input 딕셔너리의 최상위 키 'subagent_type'을 우선 확인하고,
    없는 경우 'prompt' 문자열에서 파싱을 시도한다.

    Args:
        tool_input: Task 도구의 tool_input 딕셔너리

    Returns:
        추출된 subagent_type 문자열. 찾지 못한 경우 빈 문자열.
    """
    # 최상위 키 우선 확인
    subagent_type = tool_input.get("subagent_type", "")
    if subagent_type:
        return str(subagent_type).strip()

    # prompt 문자열에서 폴백 파싱
    prompt = tool_input.get("prompt", "")
    if not isinstance(prompt, str):
        return ""

    # subagent_type="..." 또는 subagent_type='...' 패턴 탐색
    import re
    pattern = r'subagent_type\s*=\s*["\']([^"\']+)["\']'
    match = re.search(pattern, prompt)
    if match:
        return match.group(1).strip()

    return ""


def main() -> None:
    """메인 세션 조사 목적 서브에이전트 차단 Hook의 진입점.

    stdin에서 JSON을 읽어 Task 도구 사용 시 subagent_type이 조사 목적
    (Explore, general-purpose)이거나 허용 목록에 없는 미지정값인 경우,
    현재 세션이 워크플로우 세션(P:T-* 윈도우)인지 확인하고,
    메인 세션이면 deny 응답을 출력하여 서브에이전트 호출을 차단한다.
    비tmux 환경에서도 차단한다.
    """
    # .claude.workflow/.settings(.env 폴백)에서 설정 로드
    hook_flag = os.environ.get("HOOK_AGENT_INVESTIGATION_GUARD") or read_env("HOOK_AGENT_INVESTIGATION_GUARD")

    # Hook disable check (false = disabled)
    if hook_flag in ("false", "0"):
        sys.exit(0)

    # stdin에서 JSON 읽기
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    tool_name = data.get("tool_name", "")

    # Task 도구가 아니면 통과
    if tool_name != "Task":
        sys.exit(0)

    tool_input = data.get("tool_input", {})
    if not isinstance(tool_input, dict):
        sys.exit(0)

    # subagent_type 추출
    subagent_type = _extract_subagent_type(tool_input)

    # 허용 목록에 포함된 subagent_type은 세션 무관하게 통과
    if subagent_type in _ALLOWED_SUBAGENT_TYPES:
        sys.exit(0)

    # 허용 목록 외 subagent_type (Explore, general-purpose, 빈값 등)은 차단 후보
    # TMUX_PANE 환경변수 확인
    tmux_pane = os.environ.get("TMUX_PANE")
    if not tmux_pane:
        # 비tmux 환경에서는 차단
        _deny(AGENT_INVESTIGATION_MAIN_SESSION_DENIED.format(subagent_type=repr(subagent_type)))

    # tmux 윈도우명 조회
    window_name = _get_current_window_name()

    # 윈도우명 조회 실패 시 안전 차단 (보수적 접근)
    if window_name is None:
        _deny(AGENT_INVESTIGATION_WINDOW_QUERY_FAILED.format(subagent_type=repr(subagent_type)))

    # 워크플로우 세션(P:T-* 접두사)이면 통과
    if window_name.startswith(_WORKFLOW_WINDOW_PREFIX):
        sys.exit(0)

    # 메인 세션이면 차단
    _deny(AGENT_INVESTIGATION_MAIN_SESSION_DENIED.format(subagent_type=repr(subagent_type)))


if __name__ == "__main__":
    main()
