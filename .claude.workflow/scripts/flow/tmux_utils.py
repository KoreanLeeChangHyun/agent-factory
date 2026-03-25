"""tmux 윈도우 관련 공유 유틸리티."""

from __future__ import annotations

import os
import subprocess

__all__ = [
    "get_current_window_name",
    "WINDOW_PREFIX_P",
    "MAIN_WINDOW_DEFAULT",
]

# tmux 윈도우명 접두사
WINDOW_PREFIX_P: str = "P:"
MAIN_WINDOW_DEFAULT: str = "main"


def get_current_window_name() -> str:
    """현재 프로세스가 속한 tmux 윈도우 이름을 반환한다.

    TMUX_PANE 환경변수를 사용하여 프로세스가 실제로 실행 중인 pane의
    윈도우 이름을 조회한다. TMUX_PANE이 없으면 활성 윈도우 이름을 반환한다.

    Returns:
        현재 윈도우 이름 문자열. 실패 시 빈 문자열.
    """
    tmux_pane = os.environ.get("TMUX_PANE")
    if tmux_pane:
        result = subprocess.run(
            ["tmux", "display-message", "-t", tmux_pane, "-p", "#W"],
            capture_output=True,
            text=True,
        )
    else:
        result = subprocess.run(
            ["tmux", "display-message", "-p", "#W"],
            capture_output=True,
            text=True,
        )
    if result.returncode == 0:
        return result.stdout.strip()
    return ""
