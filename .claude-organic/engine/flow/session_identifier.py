"""session_identifier.py - 세션 유형 식별 추상화 레이어.

워크플로우 세션과 메인 세션을 구분하는 통합 인터페이스를 제공한다.
환경변수(_WF_SESSION_TYPE, _WF_TICKET_ID) 우선 경로와
TMUX_PANE 기반 폴백 경로를 단일 API로 추상화한다.

세션 식별 결정 흐름:
  1. _WF_SESSION_TYPE 환경변수가 존재하면 그 값을 즉시 반환한다.
  2. TMUX_PANE 환경변수가 존재하면 tmux display-message로 윈도우명을
     조회하여 P:T-* 접두사 여부로 판별한다.
  3. 둘 다 없으면 "unknown"을 반환한다.

하위호환:
  WINDOW_PREFIX_P, MAIN_WINDOW_DEFAULT 상수를 이관하여
  기존 tmux_utils.py 소비 코드가 이 모듈로 전환할 수 있다.
"""

from __future__ import annotations

import os
import subprocess

__all__ = [
    "get_session_type",
    "is_workflow_session",
    "get_session_ticket_id",
    "WINDOW_PREFIX_P",
    "MAIN_WINDOW_DEFAULT",
]

# ---------------------------------------------------------------------------
# 하위호환 상수 (tmux_utils.py에서 이관)
# ---------------------------------------------------------------------------

WINDOW_PREFIX_P: str = "P:"
"""tmux 워크플로우 윈도우명 접두사."""

MAIN_WINDOW_DEFAULT: str = "main"
"""메인 세션 기본 윈도우명."""

# ---------------------------------------------------------------------------
# 환경변수 키
# ---------------------------------------------------------------------------

_ENV_SESSION_TYPE: str = "_WF_SESSION_TYPE"
"""세션 유형 환경변수 키. 값: "workflow", "main"."""

_ENV_TICKET_ID: str = "_WF_TICKET_ID"
"""티켓 ID 환경변수 키. 값: "T-NNN"."""

# ---------------------------------------------------------------------------
# 세션 유형 상수
# ---------------------------------------------------------------------------

SESSION_TYPE_WORKFLOW: str = "workflow"
SESSION_TYPE_MAIN: str = "main"
SESSION_TYPE_UNKNOWN: str = "unknown"

# ---------------------------------------------------------------------------
# 내부 헬퍼
# ---------------------------------------------------------------------------


def _get_current_window_name() -> str:
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


# ---------------------------------------------------------------------------
# 공개 API
# ---------------------------------------------------------------------------


def get_session_type() -> str:
    """현재 세션의 유형을 반환한다.

    결정 우선순위:
      1. ``_WF_SESSION_TYPE`` 환경변수 값 (설정되어 있으면 즉시 반환)
      2. ``TMUX_PANE`` 환경변수가 있으면 tmux 윈도우명을 조회하여
         ``P:T-*`` 접두사면 ``"workflow"``, 아니면 ``"main"``
      3. 둘 다 없으면 ``"unknown"``

    Returns:
        ``"workflow"`` | ``"main"`` | ``"unknown"``
    """
    # 1) 환경변수 우선 경로
    env_type = os.environ.get(_ENV_SESSION_TYPE, "").strip().lower()
    if env_type:
        return env_type

    # 2) TMUX_PANE 폴백 경로
    tmux_pane = os.environ.get("TMUX_PANE")
    if not tmux_pane:
        return SESSION_TYPE_UNKNOWN

    window_name = _get_current_window_name()
    if window_name.startswith(f"{WINDOW_PREFIX_P}T-"):
        return SESSION_TYPE_WORKFLOW
    return SESSION_TYPE_MAIN


def is_workflow_session() -> bool:
    """현재 세션이 워크플로우 세션인지 판별한다.

    ``get_session_type()`` 의 결과가 ``"workflow"`` 인지 확인하는
    편의 래퍼이다.

    Returns:
        워크플로우 세션이면 ``True``, 그 외 ``False``.
    """
    return get_session_type() == SESSION_TYPE_WORKFLOW


def get_session_ticket_id() -> str | None:
    """현재 세션의 활성 티켓 ID를 반환한다.

    결정 우선순위:
      1. ``_WF_TICKET_ID`` 환경변수 값 (설정되어 있으면 즉시 반환)
      2. ``TMUX_PANE`` 환경변수가 있으면 tmux 윈도우명에서
         ``P:T-NNN`` 패턴을 파싱하여 ``T-NNN`` 반환
      3. 추출 실패 시 ``None``

    Returns:
        티켓 ID 문자열 (예: ``"T-001"``). 추출 실패 시 ``None``.
    """
    # 1) 환경변수 우선 경로
    env_ticket = os.environ.get(_ENV_TICKET_ID, "").strip()
    if env_ticket:
        return env_ticket

    # 2) TMUX_PANE 폴백 경로
    tmux_pane = os.environ.get("TMUX_PANE")
    if not tmux_pane:
        return None

    window_name = _get_current_window_name()
    prefix = f"{WINDOW_PREFIX_P}T-"
    if not window_name.startswith(prefix):
        return None

    # "P:" 접두사를 제거하여 "T-NNN" 부분만 반환
    return window_name[len(WINDOW_PREFIX_P):]
