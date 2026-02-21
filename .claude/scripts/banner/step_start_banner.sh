#!/usr/bin/env bash
# step_start_banner.sh - 워크플로우 단계 시작 배너 출력
#
# 사용법:
#   step_start_banner.sh INIT none <command>                          # INIT 시작
#   step_start_banner.sh <registryKey> <phase>                        # 일반 시작
#   step_start_banner.sh <registryKey> WORK-PHASE <N> "<taskIds>" <mode>  # WORK-PHASE 서브배너
#
# 예시:
#   step_start_banner.sh INIT none prompt
#   banner.sh 20260219-042258 WORK
#   banner.sh 20260219-042258 WORK-PHASE 0 "T1,T2" parallel

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
ARG1="${1:-}"
PHASE="${2:-}"

if [[ -z "$ARG1" || -z "$PHASE" ]]; then
    echo "사용법: step_start_banner.sh <registryKey|INIT> <phase> [args...]" >&2
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

# ─── 프로그레스 바 ───
get_progress() {
    case "$1" in
        INIT)   echo "${C_RED}${C_BOLD}■${C_RESET}${C_GRAY}□□□□${C_RESET}" ;;
        PLAN)   echo "${C_RED}■${C_BLUE}${C_BOLD}■${C_RESET}${C_GRAY}□□□${C_RESET}" ;;
        WORK)   echo "${C_RED}■${C_BLUE}■${C_GREEN}${C_BOLD}■${C_RESET}${C_GRAY}□□${C_RESET}" ;;
        REPORT) echo "${C_RED}■${C_BLUE}■${C_GREEN}■${C_PURPLE}${C_BOLD}■${C_RESET}${C_GRAY}□${C_RESET}" ;;
        DONE)   echo "${C_RED}■${C_BLUE}■${C_GREEN}■${C_PURPLE}■${C_YELLOW}${C_BOLD}■${C_RESET}" ;;
        *)      echo "${C_GRAY}□□□□□${C_RESET}" ;;
    esac
}

# ─── WORK-PHASE 서브배너 ───
if [[ "$PHASE" == "WORK-PHASE" ]]; then
    WP_NUM="${3:-}"
    WP_TASKS="${4:-}"
    WP_MODE="${5:-}"
    # mode 검증: parallel|sequential 만 허용, 그 외(full 등)는 sequential 폴백
    if [[ "$WP_MODE" != "parallel" && "$WP_MODE" != "sequential" ]]; then
        WP_MODE="sequential"
    fi
    echo -e "    ${C_GREEN}►${C_RESET} ${C_BOLD}Phase ${WP_NUM}${C_RESET}  ${C_DIM}${WP_TASKS}${C_RESET}  ${C_GRAY}${WP_MODE}${C_RESET}"
    exit 0
fi

# ─── registryKey → workDir/context 해석 ───
WORK_DIR=""
WORK_ID=""
TITLE=""

# INIT 시작은 특별 처리 (아직 workDir 없음)
# 호출 형식: banner.sh INIT none <command>
if [[ "$ARG1" == "INIT" ]]; then
    PHASE="INIT"
    WORK_ID="none"
    TITLE="${3:-}"  # command명이 title 위치에 옴
else
    REGISTRY_KEY="$ARG1"
    REGISTRY_FILE="$PROJECT_ROOT/.workflow/registry.json"

    # 1차: registry.json에서 조회
    if [[ -f "$REGISTRY_FILE" ]]; then
        WORK_DIR=$(python3 -c "
import json
try:
    d=json.load(open('$REGISTRY_FILE'))
    print(d.get('$REGISTRY_KEY',{}).get('workDir',''))
except: pass
" 2>/dev/null || true)
    fi

    # 2차: 디렉토리 탐색 폴백
    if [[ -z "$WORK_DIR" ]]; then
        BASE_DIR="$PROJECT_ROOT/.workflow/$REGISTRY_KEY"
        if [[ -d "$BASE_DIR" ]]; then
            for WNAME_DIR in "$BASE_DIR"/*/; do
                [[ -d "$WNAME_DIR" ]] || continue
                for CMD_DIR in "$WNAME_DIR"*/; do
                    [[ -d "$CMD_DIR" ]] || continue
                    if [[ -f "$CMD_DIR/.context.json" ]]; then
                        WORK_DIR=".workflow/$REGISTRY_KEY/$(basename "$(dirname "$CMD_DIR")")/$(basename "$CMD_DIR")"
                        break 2
                    fi
                done
            done
        fi
    fi

    # context.json에서 workId, title 읽기
    if [[ -n "$WORK_DIR" ]]; then
        ABS_WORK_DIR="$PROJECT_ROOT/$WORK_DIR"
        CTX_FILE="$ABS_WORK_DIR/.context.json"
        if [[ -f "$CTX_FILE" ]]; then
            eval "$(python3 -c "
import json
try:
    d=json.load(open('$CTX_FILE'))
    wid=d.get('workId','')
    ttl=d.get('title','').replace(\"'\",\"\")
    print(f\"WORK_ID='{wid}'\")
    print(f\"TITLE='{ttl}'\")
except: pass
" 2>/dev/null || true)"
        fi
    fi

    WORK_ID="${WORK_ID:-none}"
    TITLE="${TITLE:-unknown}"
fi

# ─── INIT 시작 시 .done-marker 제거 ───
if [[ "$PHASE" == "INIT" ]]; then
    DONE_MARKER="$PROJECT_ROOT/.workflow/.done-marker"
    rm -f "$DONE_MARKER" 2>/dev/null || true
fi

# ─── 시작 배너 출력 ───
COLOR=$(get_color "$PHASE")
PROGRESS=$(get_progress "$PHASE")

# 배너 폭 계산 (고정 75)
WIDTH=75
LINE=$(printf '─%.0s' $(seq 1 $WIDTH))

echo ""
echo -e "${COLOR}┌${LINE}┐${C_RESET}"
if [[ "$WORK_ID" == "none" ]]; then
    echo -e "  ${PROGRESS}  ${COLOR}${C_BOLD}${PHASE}${C_RESET}  ${TITLE}"
else
    echo -e "  ${PROGRESS}  ${COLOR}${C_BOLD}${PHASE}${C_RESET}  ${WORK_ID} · ${TITLE}"
fi
echo -e "${COLOR}└${LINE}┘${C_RESET}"
