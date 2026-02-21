#!/usr/bin/env bash
# step_end_banner.sh - 워크플로우 단계 완료 메시지 출력
#
# 사용법:
#   step_end_banner.sh <registryKey> <phase>          # 일반 단계 완료
#   step_end_banner.sh <registryKey> DONE done        # 최종 완료
#
# 예시:
#   step_end_banner.sh 20260219-042258 WORK
#   step_end_banner.sh 20260219-042258 REPORT
#   step_end_banner.sh 20260219-042258 DONE done

set -euo pipefail

# ─── ANSI 색상 ───
C_RED='\033[0;31m'
C_BLUE='\033[0;34m'
C_GREEN='\033[0;32m'
C_PURPLE='\033[0;35m'
C_YELLOW='\033[0;33m'
C_CYAN='\033[0;36m'
C_BOLD='\033[1m'
C_DIM='\033[2m'
C_RESET='\033[0m'

# ─── 인자 파싱 ───
REGISTRY_KEY="${1:-}"
PHASE="${2:-}"
STATUS="${3:-}"

if [[ -z "$REGISTRY_KEY" || -z "$PHASE" ]]; then
    echo "사용법: step_end_banner.sh <registryKey> <phase> [done]" >&2
    exit 0
fi

# ─── 프로젝트 루트 해석 ───
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"

# ─── registryKey → workDir 해석 ───
REGISTRY_FILE="$PROJECT_ROOT/.workflow/registry.json"
WORK_DIR=""
WORK_ID=""
TITLE=""
COMMAND=""

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

# 2차: 레지스트리에 없으면 디렉토리 탐색 (done 에이전트가 unregister 후 호출되는 경우)
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

# workDir에서 .context.json 읽기
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
    cmd=d.get('command','')
    print(f\"WORK_ID='{wid}'\")
    print(f\"TITLE='{ttl}'\")
    print(f\"COMMAND='{cmd}'\")
except: pass
" 2>/dev/null || true)"
    fi
fi

# 폴백
WORK_ID="${WORK_ID:-none}"
TITLE="${TITLE:-unknown}"

# ─── phase별 색상 ───
get_color() {
    case "$1" in
        INIT)   echo "$C_RED" ;;
        PLAN)   echo "$C_BLUE" ;;
        WORK)   echo "$C_GREEN" ;;
        REPORT) echo "$C_PURPLE" ;;
        DONE)   echo "$C_YELLOW" ;;
        *)      echo '\033[0;37m' ;;
    esac
}

COLOR=$(get_color "$PHASE")

# ─── phase별 기본 doc_path ───
get_doc_path() {
    case "$1" in
        PLAN)   echo "$WORK_DIR/plan.md" ;;
        WORK)   echo "$WORK_DIR/work/" ;;
        REPORT) echo "$WORK_DIR/report.md" ;;
        *)      echo "" ;;
    esac
}

# ─── DONE 최종 완료 배너 ───
if [[ "$PHASE" == "DONE" && -n "$STATUS" ]]; then
    echo ""
    CMD_LABEL=""
    if [[ -n "$COMMAND" ]]; then
        CMD_LABEL=" (${C_CYAN}${COMMAND}${C_RESET})"
    fi
    echo -e "  ${C_YELLOW}${C_BOLD}[OK]${C_RESET}  ${WORK_ID} · ${TITLE}${CMD_LABEL} ${C_YELLOW}워크플로우 완료${C_RESET}"
    echo ""

    # .done-marker 생성
    DONE_MARKER="$PROJECT_ROOT/.workflow/.done-marker"
    mkdir -p "$(dirname "$DONE_MARKER")"
    touch "$DONE_MARKER"

    # Slack 완료 알림 (비동기, 비차단)
    if [[ -n "$WORK_DIR" ]]; then
        REPORT_PATH=""
        if [[ -f "$PROJECT_ROOT/$WORK_DIR/report.md" ]]; then
            REPORT_PATH="$WORK_DIR/report.md"
        fi
        SLACK_PY="$SCRIPT_DIR/../../slack/slack_notify.py"
        if [[ -f "$SLACK_PY" ]]; then
            python3 "$SLACK_PY" "$WORK_DIR" "완료" "$REPORT_PATH" "" &>/dev/null &
        fi
    fi
    exit 0
fi

# ─── 일반 단계 완료 배너 ───
DOC_PATH=$(get_doc_path "$PHASE")

echo -e "${COLOR}  ✓ ${C_BOLD}${PHASE}${C_RESET}  ${C_DIM}${WORK_ID} · ${TITLE}${C_RESET}"
if [[ -n "$DOC_PATH" ]]; then
    echo -e "${COLOR}  ✓ ${C_DIM}${DOC_PATH}${C_RESET}"
fi
echo -e "${COLOR}  ✓ ${C_BOLD}${PHASE} DONE${C_RESET}"
