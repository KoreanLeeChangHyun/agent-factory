#!/usr/bin/env bash
# flow_update_banner.sh - 워크플로우 상태 전이 시각화 출력
#
# DEPRECATED: 이 스크립트는 update_state.py _print_state_banner()로 대체됨.
# update_state.py가 상태 전이 시 내부적으로 배너를 출력하므로 이 스크립트는 더 이상 호출되지 않음.
#
# 사용법:
#   flow_update_banner.sh <registryKey> <fromPhase> <toPhase>
#
# 예시:
#   flow_update_banner.sh 20260219-042258 PLAN WORK
#   flow_update_banner.sh 20260219-042258 WORK REPORT

set -euo pipefail

# ─── 인자 파싱 ───
REGISTRY_KEY="${1:-}"
FROM_PHASE="${2:-}"
TO_PHASE="${3:-}"

if [[ -z "$REGISTRY_KEY" || -z "$FROM_PHASE" || -z "$TO_PHASE" ]]; then
    echo "사용법: flow_update_banner.sh <registryKey> <fromPhase> <toPhase>" >&2
    exit 0
fi

# ─── 공통 색상/유틸리티 로드 ───
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../data/colors.sh"

# ─── 타임스탬프 생성 ───
TIMESTAMP=$(date +%H:%M:%S 2>/dev/null || echo "")

# ─── 상태 전이 출력 ───
COLOR_FROM=$(get_color "$FROM_PHASE")
COLOR_TO=$(get_color "$TO_PHASE")
echo -e "  ⟫ ${COLOR_FROM}${FROM_PHASE}${C_RESET} → ${COLOR_TO}${TO_PHASE}${C_RESET}  ${C_DIM}${TIMESTAMP}${C_RESET}"
