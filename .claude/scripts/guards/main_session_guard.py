#!/usr/bin/env -S python3 -u
"""메인 세션 Write/Edit 차단 가드 Hook 스크립트.

PreToolUse(Write|Edit) 이벤트에서 현재 tmux 윈도우가 워크플로우 세션
(P:T-* 접두사)이 아닌 메인 세션이면 코드 수정을 차단한다.
비tmux 환경(TMUX_PANE 미설정)에서도 차단한다.

주요 함수:
    main: Hook 진입점, stdin JSON 파싱 후 메인 세션 Write/Edit 차단

입력: stdin으로 JSON (tool_name, tool_input)
출력: 차단 시 hookSpecificOutput JSON, 통과 시 빈 출력

토글: 환경변수 HOOK_MAIN_SESSION_GUARD (false/0 = 비활성, 기본 활성)
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

# 워크플로우 세션 윈도우명 접두사
_WORKFLOW_WINDOW_PREFIX = "P:T-"


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


def main() -> None:
    """메인 세션 Write/Edit 차단 Hook의 진입점.

    stdin에서 JSON을 읽어 Write/Edit 도구 사용 시 현재 세션이
    워크플로우 세션(P:T-* 윈도우)인지 확인하고,
    메인 세션이면 deny 응답을 출력하여 코드 수정을 차단한다.
    비tmux 환경에서도 차단한다.
    """
    # .claude.env에서 설정 로드
    hook_flag = os.environ.get("HOOK_MAIN_SESSION_GUARD") or read_env("HOOK_MAIN_SESSION_GUARD")

    # Hook disable check (false = disabled)
    if hook_flag in ("false", "0"):
        sys.exit(0)

    # stdin에서 JSON 읽기
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    tool_name = data.get("tool_name", "")

    # Write, Edit가 아니면 통과
    if tool_name not in ("Write", "Edit"):
        sys.exit(0)

    # TMUX_PANE 환경변수 확인
    tmux_pane = os.environ.get("TMUX_PANE")
    if not tmux_pane:
        # 비tmux 환경에서는 차단
        _deny(
            "비tmux 환경에서의 코드 수정이 차단되었습니다. "
            "워크플로우 세션(tmux P:T-* 윈도우)에서 작업하세요."
        )

    # tmux 윈도우명 조회
    window_name = _get_current_window_name()

    # 윈도우명 조회 실패 시 안전 차단 (보수적 접근)
    if window_name is None:
        _deny(
            "tmux 윈도우명 조회에 실패하여 코드 수정이 차단되었습니다. "
            "워크플로우 세션(tmux P:T-* 윈도우)에서 작업하세요."
        )

    # 워크플로우 세션(P:T-* 접두사)이면 통과
    if window_name.startswith(_WORKFLOW_WINDOW_PREFIX):
        sys.exit(0)

    # 메인 세션이면 차단
    _deny(
        f"메인 세션(윈도우: {window_name})에서의 코드 수정이 차단되었습니다. "
        "워크플로우 세션(tmux P:T-* 윈도우)에서 작업하세요."
    )


if __name__ == "__main__":
    main()
