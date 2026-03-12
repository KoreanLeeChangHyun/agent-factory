#!/usr/bin/env -S python3 -u
"""session_start_system_prompt.py - SessionStart hook으로 세션별 system-prompt를 자동 주입한다.

tmux 윈도우 이름(T-* 여부)으로 메인/워크플로우 세션을 분기하여
system-prompt.xml(메인용) 또는 system-prompt-wf.xml(워크플로우용)을 stdout으로 출력한다.

동작:
  - TMUX_PANE 환경변수가 있으면 tmux display-message로 현재 윈도우 이름을 조회한다.
  - TMUX_PANE이 없으면(비tmux 환경) 메인용으로 폴백한다.
  - 윈도우 이름이 T- 접두사로 시작하면 system-prompt-wf.xml을 출력한다.
  - 그 외(메인 세션)이면 system-prompt.xml을 출력한다.
  - 대상 파일이 존재하지 않으면 에러 없이 exit 0으로 종료한다.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _get_current_window_name() -> str:
    """현재 프로세스가 속한 tmux 윈도우 이름을 반환한다.

    TMUX_PANE 환경변수를 사용하여 프로세스가 실제로 실행 중인 pane의
    윈도우 이름을 조회한다. TMUX_PANE이 없으면 활성 윈도우 이름을 반환한다.

    Returns:
        현재 윈도우 이름 문자열. 실패 시 빈 문자열.
    """
    tmux_pane = os.environ.get("TMUX_PANE")
    if tmux_pane:
        cmd = ["tmux", "display-message", "-t", tmux_pane, "-p", "#W"]
    else:
        cmd = ["tmux", "display-message", "-p", "#W"]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        return result.stdout.strip()
    return ""


def _is_workflow_session() -> bool:
    """현재 세션이 워크플로우 세션인지 판별한다.

    TMUX_PANE 환경변수가 있으면 tmux 윈도우 이름을 조회하여
    T- 접두사 여부로 판별한다. TMUX_PANE이 없으면 False를 반환한다.

    Returns:
        워크플로우 세션(T-* 윈도우)이면 True, 그 외 False.
    """
    tmux_pane = os.environ.get("TMUX_PANE")
    if not tmux_pane:
        return False

    window_name = _get_current_window_name()
    return window_name.startswith("T-")


def main() -> None:
    """세션 유형을 판별하고 대응하는 system-prompt XML 파일을 stdout에 출력한다."""
    # 프로젝트 루트: .claude/scripts/hooks/ 기준 ../../..
    project_root = Path(__file__).parent.parent.parent.parent

    if _is_workflow_session():
        prompt_file = project_root / ".claude" / "system-prompt-wf.xml"
    else:
        prompt_file = project_root / ".claude" / "system-prompt.xml"

    # 파일이 없으면 에러 없이 종료
    if not prompt_file.exists():
        sys.exit(0)

    content = prompt_file.read_text(encoding="utf-8")
    print(content, end="")
    sys.exit(0)


if __name__ == "__main__":
    main()
