#!/usr/bin/env bash
# colors.sh - Shell 배너 스크립트 공통 ANSI 색상 변수 및 유틸리티
# 이 파일은 Shell 배너 스크립트용입니다. Python 코드에서는 data.colors를 import하세요.
#
# 사용법:
#   source "$SCRIPT_DIR/../data/colors.sh"
#
# 제공 변수:
#   C_RED, C_BLUE, C_GREEN, C_PURPLE, C_YELLOW, C_CYAN, C_GRAY, C_BOLD, C_DIM, C_RESET
#   BANNER_WIDTH
#
# 제공 함수:
#   get_color <PHASE>  - phase별 ANSI 색상 코드를 반환

# ─── ANSI 색상 ───
C_RED='\033[0;31m'
C_BLUE='\033[0;34m'
C_GREEN='\033[0;32m'
C_PURPLE='\033[0;35m'
C_YELLOW='\033[0;33m'
C_CYAN='\033[0;36m'
C_GRAY='\033[0;90m'
C_BOLD='\033[1m'
C_DIM='\033[2m'
C_RESET='\033[0m'

# ─── 배너 폭 ───
BANNER_WIDTH=75

# ─── phase별 색상 ───
get_color() {
    case "$1" in
        INIT)                       echo "$C_RED" ;;
        PLAN)                       echo "$C_BLUE" ;;
        WORK)                       echo "$C_GREEN" ;;
        REPORT)                     echo "$C_PURPLE" ;;
        DONE|COMPLETED)             echo "$C_YELLOW" ;;
        CANCELLED|STALE|FAILED)     echo "$C_GRAY" ;;
        *)                          echo '\033[0;37m' ;;
    esac
}
