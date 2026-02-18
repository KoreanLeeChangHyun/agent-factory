#!/bin/bash
# workflow-info.sh - 워크플로우 정보 조회 스크립트
#
# 사용법:
#   wf-info 20260208-135954                                          # YYYYMMDD-HHMMSS (registry.json에서 workDir 조회)
#   wf-info .workflow/20260208-135954/디렉터리-구조-변경/implement    # workDir 전체 경로
#   wf-info .workflow/20260208-135954                                 # 레거시 플랫 구조 호환
#
# 지정된 워크플로우의 주요 파일 경로를 터미널에 출력합니다.
# VSCode 터미널에서 절대 경로를 Ctrl+Click으로 열 수 있습니다.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# --- 색상 코드 ---
BOLD='\033[1m'
DIM='\033[2m'
RESET='\033[0m'
GRAY='\033[0;90m'
YELLOW='\033[0;33m'
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'

# --- 인자 처리 ---
if [ $# -lt 1 ] || [ -z "$1" ]; then
    echo -e "${RED}사용법: wf-info <워크플로우ID 또는 workDir 경로>${RESET}"
    echo -e "${DIM}  예: wf-info 20260208-135954${RESET}"
    echo -e "${DIM}  예: wf-info .workflow/20260208-135954/디렉터리-구조-변경/implement${RESET}"
    exit 1
fi

INPUT="$1"

# --- 워크플로우 디렉토리 결정 ---
# .workflow/ 접두사가 있으면 그대로, 없으면 추가
if [[ "$INPUT" == .workflow/* ]]; then
    WORK_DIR="$INPUT"
elif [[ "$INPUT" == /* ]]; then
    # 절대 경로
    WORK_DIR="$INPUT"
else
    # YYYYMMDD-HHMMSS 형식: registry.json에서 workDir 조회 시도
    REGISTRY_FILE="${PROJECT_ROOT}/.workflow/registry.json"
    RESOLVED_DIR=""
    if [ -f "$REGISTRY_FILE" ] && command -v python3 &>/dev/null; then
        RESOLVED_DIR=$(WF_REG="$REGISTRY_FILE" WF_KEY="$INPUT" python3 -c "
import json, os, sys
reg_file = os.environ['WF_REG']
key = os.environ['WF_KEY']
try:
    with open(reg_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    if key in data and 'workDir' in data[key]:
        print(data[key]['workDir'])
except Exception:
    pass
" 2>/dev/null || true)
    fi

    if [ -n "$RESOLVED_DIR" ]; then
        WORK_DIR="$RESOLVED_DIR"
    else
        # 폴백: 레거시 플랫 구조 (.workflow/YYYYMMDD-HHMMSS)
        WORK_DIR=".workflow/$INPUT"
    fi
fi

# 절대 경로 계산
if [[ "$WORK_DIR" == /* ]]; then
    ABS_WORK_DIR="$WORK_DIR"
else
    ABS_WORK_DIR="${PROJECT_ROOT}/${WORK_DIR}"
fi

# 디렉토리 존재 확인
if [ ! -d "$ABS_WORK_DIR" ]; then
    echo -e "${RED}[ERROR] 워크플로우 디렉토리가 존재하지 않습니다: ${WORK_DIR}${RESET}"
    exit 1
fi

# --- .context.json 읽기 ---
CONTEXT_FILE="${ABS_WORK_DIR}/.context.json"
TITLE=""
WORK_ID=""
COMMAND=""

if [ -f "$CONTEXT_FILE" ]; then
    if command -v python3 &>/dev/null; then
        TITLE=$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(d.get('title',''))" "$CONTEXT_FILE" 2>/dev/null || true)
        WORK_ID=$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(d.get('workId',''))" "$CONTEXT_FILE" 2>/dev/null || true)
        COMMAND=$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(d.get('command',''))" "$CONTEXT_FILE" 2>/dev/null || true)
    fi
fi

# 폴백: basename에서 ID 추출
if [ -z "$WORK_ID" ]; then
    WORK_ID=$(basename "$ABS_WORK_DIR")
fi
[ -z "$TITLE" ] && TITLE="(제목 없음)"
[ -z "$COMMAND" ] && COMMAND="(알 수 없음)"

# --- status.json 읽기 ---
STATUS_FILE="${ABS_WORK_DIR}/status.json"
PHASE=""

if [ -f "$STATUS_FILE" ]; then
    if command -v python3 &>/dev/null; then
        PHASE=$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(d.get('phase',''))" "$STATUS_FILE" 2>/dev/null || true)
    fi
fi
[ -z "$PHASE" ] && PHASE="(알 수 없음)"

# --- Phase 색상 ---
phase_color() {
    case "$1" in
        INIT)       echo "$RED" ;;
        PLAN)       echo "$BLUE" ;;
        WORK)       echo "$GREEN" ;;
        REPORT)     echo "$PURPLE" ;;
        COMPLETED)  echo "$YELLOW" ;;
        *)          echo "$GRAY" ;;
    esac
}

PHASE_COLOR=$(phase_color "$PHASE")

# --- 파일 존재 확인 함수 ---
file_status() {
    local abs_path="$1"
    if [ -e "$abs_path" ]; then
        echo "exists"
    else
        echo "missing"
    fi
}

# --- 주요 경로 ---
PLAN_PATH="${ABS_WORK_DIR}/plan.md"
WORK_PATH="${ABS_WORK_DIR}/work/"
REPORT_PATH="${ABS_WORK_DIR}/report.md"

PLAN_STATUS=$(file_status "$PLAN_PATH")
WORK_STATUS=$(file_status "$WORK_PATH")
REPORT_STATUS=$(file_status "$REPORT_PATH")

# work/ 내 파일 수 카운트
WORK_FILE_COUNT=0
if [ -d "$WORK_PATH" ]; then
    WORK_FILE_COUNT=$(find "$WORK_PATH" -type f 2>/dev/null | wc -l | tr -d ' ')
fi

# --- 구분선 ---
SEPARATOR_WIDTH=60
SEPARATOR=$(printf '%.0s─' $(seq 1 $SEPARATOR_WIDTH))

# --- 출력 ---
echo ""
echo -e "  ${BOLD}${WORK_ID}${RESET} ${DIM}·${RESET} ${TITLE}"
echo -e "  ${DIM}${SEPARATOR}${RESET}"
echo -e "  ${DIM}명령어${RESET}  ${CYAN}${COMMAND}${RESET}    ${DIM}상태${RESET}  ${PHASE_COLOR}${BOLD}${PHASE}${RESET}"
echo -e "  ${DIM}${SEPARATOR}${RESET}"

# plan.md
if [ "$PLAN_STATUS" = "exists" ]; then
    echo -e "  ${GREEN}●${RESET} plan.md   ${DIM}→${RESET}  ${PLAN_PATH}"
else
    echo -e "  ${RED}○${RESET} plan.md   ${DIM}→${RESET}  ${DIM}(없음)${RESET}"
fi

# work/
if [ "$WORK_STATUS" = "exists" ]; then
    echo -e "  ${GREEN}●${RESET} work/     ${DIM}→${RESET}  ${WORK_PATH}  ${DIM}(${WORK_FILE_COUNT}개 파일)${RESET}"
else
    echo -e "  ${RED}○${RESET} work/     ${DIM}→${RESET}  ${DIM}(없음)${RESET}"
fi

# report.md
if [ "$REPORT_STATUS" = "exists" ]; then
    echo -e "  ${GREEN}●${RESET} report.md ${DIM}→${RESET}  ${REPORT_PATH}"
else
    echo -e "  ${RED}○${RESET} report.md ${DIM}→${RESET}  ${DIM}(없음)${RESET}"
fi

echo ""
