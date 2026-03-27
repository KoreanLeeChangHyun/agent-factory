#!/usr/bin/env -S python3 -u
"""inject_prompt.py - SessionStart hook으로 워크플로우 세션 전용 system-prompt를 주입한다.

tmux 윈도우 이름(P:T-* 여부)으로 워크플로우 세션 여부를 판별하여
.claude.workflow/prompt/system-prompt-wf.xml을 stdout으로 출력한다.
메인 세션에서는 아무것도 출력하지 않고 즉시 exit 0으로 종료한다.
(메인 세션 정책은 CLAUDE.md + .claude/rules/workflow.md 가 담당한다.)

동작:
  - TMUX_PANE 환경변수가 있으면 tmux display-message로 현재 윈도우 이름을 조회한다.
  - 윈도우 이름이 P:T- 접두사로 시작하면 .claude.workflow/prompt/system-prompt-wf.xml을 출력한다.
  - 그 외(메인 세션 또는 비tmux 환경)이면 아무것도 출력하지 않고 exit 0으로 종료한다.
  - 대상 파일이 존재하지 않으면 에러 없이 exit 0으로 종료한다.
  - 워크플로우 세션에서 활성 티켓(T-NNN)이 감지되면, 매 응답 첫 줄에 [T-NNN] 접두사를
    출력하도록 지시하는 <ticket-prefix> XML 블록을 system-prompt 뒤에 추가로 주입한다.
"""

from __future__ import annotations

import os
import sys

_scripts_dir: str = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from common import resolve_project_root
from flow.flow_logger import append_log, resolve_work_dir_for_logging
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
    """세션 유형을 판별하고 워크플로우 세션일 때만 system-prompt-wf.xml을 stdout에 출력한다.

    메인 세션(워크플로우 세션이 아닌 경우)에서는 아무것도 출력하지 않고 즉시 종료한다.
    메인 세션 정책은 CLAUDE.md + .claude/rules/workflow.md 가 담당한다.
    """
    project_root = resolve_project_root()

    if not _is_workflow_session():
        # 메인 세션 또는 비tmux 환경: 주입할 프롬프트 없음, 즉시 종료
        sys.exit(0)

    prompt_file = os.path.join(project_root, ".claude.workflow", "prompt", "system-prompt-wf.xml")

    _log_dir = resolve_work_dir_for_logging(project_root)
    if _log_dir:
        append_log(_log_dir, "INFO", "inject_prompt: session_type=workflow")

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
