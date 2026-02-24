"""
colors.py - Shell 배너 스크립트 공통 ANSI 색상 변수 및 유틸리티의 Python 변환

colors.sh의 ANSI 색상 변수, 배너 폭 상수, phase별 색상 함수를 Python으로 변환한 모듈입니다.
이 모듈은 순수 상수와 유틸리티 함수만 정의하며, 다른 모듈을 import하지 않는 leaf 모듈입니다.

카테고리:
    ANSI 색상 변수     - C_RED, C_BLUE, C_GREEN, C_PURPLE, C_YELLOW, C_CYAN, C_GRAY, C_BOLD, C_DIM, C_RESET
    배너 폭 상수       - BANNER_WIDTH
    Phase별 색상 함수  - get_color()
"""

# =============================================================================
# ANSI 색상 변수
# =============================================================================
C_RED = "\033[0;31m"       # 빨강 - INIT phase
C_BLUE = "\033[0;34m"      # 파랑 - PLAN phase
C_GREEN = "\033[0;32m"     # 초록 - WORK phase
C_PURPLE = "\033[0;35m"    # 보라 - REPORT phase
C_YELLOW = "\033[0;33m"    # 노랑 - DONE phase
C_CYAN = "\033[0;36m"      # 시안
C_GRAY = "\033[0;90m"      # 회색 - CANCELLED/STALE/FAILED phase
C_BOLD = "\033[1m"         # 굵게
C_DIM = "\033[2m"          # 흐리게
C_RESET = "\033[0m"        # 리셋

# =============================================================================
# 배너 폭 상수
# =============================================================================
BANNER_WIDTH = 75  # 배너 출력 시 기본 가로 폭 (문자 수)

# =============================================================================
# Phase별 색상 매핑 (내부용)
# =============================================================================
_PHASE_COLOR_MAP = {
    "INIT": C_RED,
    "PLAN": C_BLUE,
    "WORK": C_GREEN,
    "REPORT": C_PURPLE,
    "STRATEGY": C_CYAN,
    "DONE": C_YELLOW,
    "CANCELLED": C_GRAY,
    "STALE": C_GRAY,
    "FAILED": C_GRAY,
}

_DEFAULT_COLOR = "\033[0;37m"  # 기본 색상 (흰색) - 매핑되지 않는 phase용


def get_color(phase: str) -> str:
    """phase별 ANSI 색상 코드를 반환한다.

    Args:
        phase: Phase 이름 (INIT, PLAN, WORK, REPORT, DONE, CANCELLED, STALE, FAILED 등)

    Returns:
        해당 phase의 ANSI 색상 코드 문자열. 매핑되지 않는 phase는 흰색(\033[0;37m]) 반환.
    """
    return _PHASE_COLOR_MAP.get(phase, _DEFAULT_COLOR)
