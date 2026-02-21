#!/usr/bin/env bash
# step_change_banner.sh - 워크플로우 상태 전이 시각화 출력
#
# 사용법:
#   step_change_banner.sh <registryKey> <fromPhase> <toPhase>
#
# 예시:
#   step_change_banner.sh 20260219-042258 PLAN WORK
#   step_change_banner.sh 20260219-042258 WORK REPORT
#   step_change_banner.sh 20260219-042258 REPORT DONE

set -euo pipefail

# ─── ANSI 색상 ───
C_RED='\033[0;31m'
C_BLUE='\033[0;34m'
C_GREEN='\033[0;32m'
C_PURPLE='\033[0;35m'
C_YELLOW='\033[0;33m'
C_GRAY='\033[0;90m'
C_BOLD='\033[1m'
C_DIM='\033[2m'
C_RESET='\033[0m'

# ─── 인자 파싱 ───
REGISTRY_KEY="${1:-}"
FROM_PHASE="${2:-}"
TO_PHASE="${3:-}"

if [[ -z "$REGISTRY_KEY" || -z "$FROM_PHASE" || -z "$TO_PHASE" ]]; then
    echo "사용법: step_change_banner.sh <registryKey> <fromPhase> <toPhase>" >&2
    exit 0
fi

# ─── 프로젝트 루트 해석 ───
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

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

# ─── 타임스탬프 생성 ───
TIMESTAMP=$(date +%H:%M:%S 2>/dev/null || echo "")

# ─── 상태 전이 출력 ───
COLOR_FROM=$(get_color "$FROM_PHASE")
COLOR_TO=$(get_color "$TO_PHASE")
echo -e "  \xe2\x9f\xab ${COLOR_FROM}${FROM_PHASE}${C_RESET} \xe2\x86\x92 ${COLOR_TO}${TO_PHASE}${C_RESET}  ${C_DIM}${TIMESTAMP}${C_RESET}"
