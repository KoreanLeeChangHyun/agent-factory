"""
constants.py - 프로젝트 공통 상수 정의

.claude/scripts/ 하위 스크립트에서 공통 사용하는 상수를 한 곳에 정의합니다.
이 모듈은 순수 상수만 정의하며, 다른 모듈을 import하지 않는 leaf 모듈입니다.

카테고리:
    ANSI 색상 코드          - C_RED, C_BLUE, C_GREEN, C_PURPLE, C_YELLOW, C_CYAN, C_GRAY, C_BOLD, C_DIM, C_RESET
    Phase별 색상 매핑       - PHASE_COLORS
    타임스탬프 정규식       - TS_PATTERN
    KST 타임존              - KST
    공통 타임아웃/제한값    - STALE_TTL_MINUTES, ZOMBIE_TTL_HOURS, REPORT_TTL_HOURS, KEEP_COUNT, WORK_NAME_MAX_LEN
    터미널 파일명 상수      - REGISTRY_FILENAME, STATUS_FILENAME, CONTEXT_FILENAME, DONE_MARKER_FILENAME, ...
    유효 명령어/모드 집합   - VALID_COMMANDS, VALID_MODES
    터미널 phase 집합       - TERMINAL_PHASES
    바이트 단위 상수        - BYTES_GB, BYTES_MB, BYTES_KB
"""

import re
from datetime import timezone, timedelta

# =============================================================================
# ANSI 색상 코드 상수
# =============================================================================
C_RED = "\033[0;31m"
C_BLUE = "\033[0;34m"
C_GREEN = "\033[0;32m"
C_PURPLE = "\033[0;35m"
C_YELLOW = "\033[0;33m"
C_CYAN = "\033[0;36m"
C_GRAY = "\033[0;90m"
C_BOLD = "\033[1m"
C_DIM = "\033[2m"
C_RESET = "\033[0m"

# =============================================================================
# Phase별 색상 매핑
# =============================================================================
PHASE_COLORS = {
    "INIT": C_RED,
    "PLAN": C_BLUE,
    "WORK": C_GREEN,
    "REPORT": C_PURPLE,
    "COMPLETED": C_GRAY,
    "STALE": C_GRAY,
    "FAILED": C_YELLOW,
    "CANCELLED": C_GRAY,
}

# =============================================================================
# YYYYMMDD-HHMMSS 패턴 정규식
# =============================================================================
TS_PATTERN = re.compile(r"^\d{8}-\d{6}$")

# =============================================================================
# KST 타임존 (UTC+9)
# =============================================================================
KST = timezone(timedelta(hours=9))

# =============================================================================
# 공통 타임아웃/제한값
# =============================================================================
STALE_TTL_MINUTES = 30
ZOMBIE_TTL_HOURS = 24
REPORT_TTL_HOURS = 1
KEEP_COUNT = 10
WORK_NAME_MAX_LEN = 20

# =============================================================================
# 터미널 파일명 상수
# =============================================================================
REGISTRY_FILENAME = "registry.json"
STATUS_FILENAME = "status.json"
CONTEXT_FILENAME = ".context.json"
DONE_MARKER_FILENAME = ".done-marker"
STOP_BLOCK_COUNTER_FILENAME = ".stop-block-counter"
BYPASS_FILENAME = "bypass"
FSM_TRANSITIONS_FILENAME = "fsm-transitions.json"

# =============================================================================
# 유효 명령어/모드 집합
# =============================================================================
VALID_COMMANDS = {"implement", "review", "research", "strategy"}
VALID_MODES = {"full", "strategy", "noplan", "noreport", "noplan+noreport"}

# =============================================================================
# 터미널 phase 집합
# =============================================================================
TERMINAL_PHASES = {"COMPLETED", "FAILED", "STALE", "CANCELLED"}

# auto_continue_guard용 비활성 phase 집합 (빈 문자열, REPORT 포함)
AUTO_CONTINUE_INACTIVE_PHASES = ("COMPLETED", "FAILED", "CANCELLED", "STALE", "", "REPORT")

# =============================================================================
# 바이트 단위 상수
# =============================================================================
BYTES_GB = 1073741824
BYTES_MB = 1048576
BYTES_KB = 1024

# =============================================================================
# 외부 API URL
# =============================================================================
SLACK_API_URL = "https://slack.com/api/chat.postMessage"

# =============================================================================
# 동기화 관련 상수
# =============================================================================
CODE_SYNC_REMOTE_REPO = "https://github.com/KoreanLeeChangHyun/claude-workflow.git"
STALE_TTL_SECONDS = STALE_TTL_MINUTES * 60
