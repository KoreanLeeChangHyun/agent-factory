#!/usr/bin/env -S python3 -u
"""session_start_system_prompt.py - SessionStart hook으로 세션별 system-prompt를 자동 주입한다.

tmux 윈도우 이름(P:T-* 여부)으로 메인/워크플로우 세션을 분기하여
system-prompt.xml(메인용) 또는 system-prompt-wf.xml(워크플로우용)을 stdout으로 출력한다.

동작:
  - TMUX_PANE 환경변수가 있으면 tmux display-message로 현재 윈도우 이름을 조회한다.
  - TMUX_PANE이 없으면(비tmux 환경) 메인용으로 폴백한다.
  - 윈도우 이름이 P:T- 접두사로 시작하면 system-prompt-wf.xml을 출력한다.
  - 그 외(메인 세션)이면 system-prompt.xml을 출력한다.
  - 대상 파일이 존재하지 않으면 에러 없이 exit 0으로 종료한다.
  - 워크플로우 세션에서 활성 티켓(T-NNN)이 감지되면, 매 응답 첫 줄에 [T-NNN] 접두사를
    출력하도록 지시하는 <ticket-prefix> XML 블록을 system-prompt 뒤에 추가로 주입한다.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from common import resolve_project_root
from flow.tmux_utils import (
    get_current_window_name,
    WINDOW_PREFIX_P,
)


def _extract_ticket_id() -> str | None:
    """현재 tmux 윈도우명에서 활성 티켓 ID(T-NNN)를 추출한다.

    tmux 윈도우 이름이 "P:T-NNN" 형식인 경우 "T-NNN" 부분을 반환한다.
    워크플로우 세션이 아니거나 추출에 실패하면 None을 반환한다.

    Returns:
        티켓 ID 문자열 (예: "T-001"). 워크플로우 세션이 아니거나 추출 실패 시 None.
    """
    tmux_pane = os.environ.get("TMUX_PANE")
    if not tmux_pane:
        return None

    window_name = get_current_window_name()
    prefix = f"{WINDOW_PREFIX_P}T-"
    if not window_name.startswith(prefix):
        return None

    # "P:" 접두사를 제거하여 "T-NNN" 부분만 반환
    return window_name[len(WINDOW_PREFIX_P):]


def _is_workflow_session() -> bool:
    """현재 세션이 워크플로우 세션인지 판별한다.

    TMUX_PANE 환경변수가 있으면 tmux 윈도우 이름을 조회하여
    P:T- 접두사 여부로 판별한다. TMUX_PANE이 없으면 False를 반환한다.

    Returns:
        워크플로우 세션(P:T-* 윈도우)이면 True, 그 외 False.
    """
    tmux_pane = os.environ.get("TMUX_PANE")
    if not tmux_pane:
        return False

    window_name = get_current_window_name()
    return window_name.startswith(f"{WINDOW_PREFIX_P}T-")


def main() -> None:
    """세션 유형을 판별하고 대응하는 system-prompt XML 파일을 stdout에 출력한다."""
    project_root = resolve_project_root()

    if _is_workflow_session():
        prompt_file = os.path.join(project_root, ".claude", "system-prompt-wf.xml")
    else:
        prompt_file = os.path.join(project_root, ".claude", "system-prompt.xml")

    # 파일이 없으면 에러 없이 종료
    if not os.path.exists(prompt_file):
        sys.exit(0)

    with open(prompt_file, encoding="utf-8") as f:
        content = f.read()

    ticket_id = _extract_ticket_id()
    if ticket_id:
        ticket_prefix_block = (
            f"\n<ticket-prefix>\n"
            f"매 응답의 첫 줄에 [{ticket_id}] 접두사를 반드시 출력하라.\n"
            f"예시: [{ticket_id}] 응답 내용...\n"
            f"</ticket-prefix>"
        )
        content = content + ticket_prefix_block

    print(content, end="")
    sys.exit(0)


if __name__ == "__main__":
    main()
