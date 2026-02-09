#!/bin/bash
# 워크플로우 단계 배너 출력 스크립트
#
# 시그니처:
#   단축 형식:  ./workflow-banner.sh <YYYYMMDD-HHMMSS> <phase> [status] [path]
#   신규 형식:  ./workflow-banner.sh <workDir> <phase> [status] [path]
#   레거시:     ./workflow-banner.sh <phase> <workId> <title> [status] [path] [workDir]
#
# 시그니처 자동 감지:
#   1번째 인자가 YYYYMMDD-HHMMSS 패턴이면 단축 방식 (registry.json에서 workDir 해석)
#   1번째 인자가 '.workflow/' 또는 '/'로 시작하면 신규 방식 (workDir 기반)
#   그렇지 않으면 레거시 방식 (positional args)
#
# 단축/신규 방식 인자:
#   workDir - YYYYMMDD-HHMMSS 또는 워크플로우 작업 디렉토리 경로
#   phase   - 워크플로우 단계 (INIT, PLAN, WORK, REPORT, DONE)
#   status  - (선택) 완료 상태 메시지. 지정 시 완료 배너 출력
#   path    - (선택) 문서 경로. 완료 배너에 보고서 링크로 표시
#             미전달 시 phase별 기본 경로 자동 추론:
#               PLAN -> ${workDir}/plan.md, WORK -> ${workDir}/work/, REPORT -> ${workDir}/report.md
#
# 레거시 방식 인자:
#   phase   - 워크플로우 단계 (INIT, PLAN, WORK, REPORT, DONE)
#   workId  - 작업 ID (예: 084248). INIT 시작 시 "none" 전달 가능
#   title   - 작업 제목 (예: 터미널-출력-명확화). INIT 시작 시 command명 전달
#   status  - (선택) 완료 상태 메시지. 지정 시 완료 배너 출력
#   path    - (선택) 문서 경로. 완료 배너에 보고서 링크로 표시
#   workDir - (선택) 워크플로우 작업 디렉토리. DONE 시 Slack 완료 알림 전송
#
# 예시 (단축):
#   PLAN 시작:  ./workflow-banner.sh 20260207-084248 PLAN
#   PLAN 완료:  ./workflow-banner.sh 20260207-084248 PLAN done          # path 자동 추론
#   PLAN 완료:  ./workflow-banner.sh 20260207-084248 PLAN done "/custom/path"  # 명시적 path (우선)
#   DONE:       ./workflow-banner.sh 20260207-084248 DONE done
#
# 예시 (신규):
#   INIT 완료:  ./workflow-banner.sh .workflow/20260207-084248/터미널-출력-명확화/implement INIT done
#   PLAN 시작:  ./workflow-banner.sh .workflow/20260207-084248/터미널-출력-명확화/implement PLAN
#
# 예시 (레거시):
#   PLAN 시작:  ./workflow-banner.sh PLAN 084248 터미널-출력-명확화
#   PLAN 완료:  ./workflow-banner.sh PLAN 084248 터미널-출력-명확화 done

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# --- YYYYMMDD-HHMMSS 단축 형식 해석 ---
# 1번째 인자가 YYYYMMDD-HHMMSS 패턴이면 registry.json에서 workDir 조회
_RESOLVED_ARG1="$1"
if [[ "$1" =~ ^[0-9]{8}-[0-9]{6}$ ]]; then
    _REG_FILE="${PROJECT_ROOT}/.workflow/registry.json"
    _RESOLVED_DIR=""
    if [ -f "$_REG_FILE" ] && command -v python3 &>/dev/null; then
        _RESOLVED_DIR=$(WF_REG="$_REG_FILE" WF_KEY="$1" python3 -c "
import json, os
try:
    with open(os.environ['WF_REG'], 'r', encoding='utf-8') as f:
        data = json.load(f)
    key = os.environ['WF_KEY']
    if key in data and 'workDir' in data[key]:
        print(data[key]['workDir'])
except Exception:
    pass
" 2>/dev/null || true)
    fi
    if [ -n "$_RESOLVED_DIR" ]; then
        _RESOLVED_ARG1="$_RESOLVED_DIR"
    else
        # 폴백 1: 중첩 디렉토리 탐색 (.workflow/YYYYMMDD-HHMMSS/<workName>/<command>/.context.json)
        _NESTED_DIR=""
        _BASE_DIR="${PROJECT_ROOT}/.workflow/$1"
        if [ -d "$_BASE_DIR" ]; then
            for _WNAME_DIR in "$_BASE_DIR"/*/; do
                [ -d "$_WNAME_DIR" ] || continue
                for _CMD_DIR in "$_WNAME_DIR"*/; do
                    [ -d "$_CMD_DIR" ] || continue
                    if [ -f "${_CMD_DIR}.context.json" ]; then
                        # 상대 경로로 변환 (.workflow/YYYYMMDD-HHMMSS/<workName>/<command>)
                        _NESTED_DIR=".workflow/$1/$(basename "$(dirname "$_CMD_DIR")")/$(basename "$_CMD_DIR")"
                        break 2
                    fi
                done
            done
        fi
        if [ -n "$_NESTED_DIR" ]; then
            _RESOLVED_ARG1="$_NESTED_DIR"
        else
            # 폴백 2: 레거시 플랫 구조
            _RESOLVED_ARG1=".workflow/$1"
        fi
    fi
fi

# --- 시그니처 감지 ---
if [[ "$_RESOLVED_ARG1" == .workflow/* ]] || [[ "$_RESOLVED_ARG1" == /* ]]; then
    # 신규 방식: <workDir> <phase> [status] [path]
    if [ $# -lt 2 ]; then
        echo "사용법: $0 <workDir> <phase> [status] [path]"
        exit 1
    fi

    WORK_DIR="$_RESOLVED_ARG1"
    PHASE="$2"
    STATUS="$3"
    DOC_PATH="$4"

    # workDir 절대 경로 계산
    if [[ "$WORK_DIR" == /* ]]; then
        _ABS_WORK_DIR="$WORK_DIR"
    else
        _ABS_WORK_DIR="${PROJECT_ROOT}/${WORK_DIR}"
    fi

    # .context.json에서 workId, title 읽기 (jq > python3 > 폴백)
    _CONTEXT_FILE="${_ABS_WORK_DIR}/.context.json"
    WORK_ID=""
    TITLE=""

    if [ -f "$_CONTEXT_FILE" ]; then
        if command -v jq &>/dev/null; then
            WORK_ID=$(jq -r '.workId // ""' "$_CONTEXT_FILE" 2>/dev/null)
            TITLE=$(jq -r '.title // ""' "$_CONTEXT_FILE" 2>/dev/null)
        elif command -v python3 &>/dev/null; then
            WORK_ID=$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(d.get('workId',''))" "$_CONTEXT_FILE" 2>/dev/null)
            TITLE=$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(d.get('title',''))" "$_CONTEXT_FILE" 2>/dev/null)
        fi
    fi

    # 폴백: .context.json 읽기 실패 시
    [ -z "$WORK_ID" ] && WORK_ID="none"
    [ -z "$TITLE" ] && TITLE="unknown"
else
    # 레거시 방식: <phase> <workId> <title> [status] [path] [workDir]
    if [ $# -lt 3 ]; then
        echo "사용법: $0 <phase> <workId> <title> [status] [path]"
        exit 1
    fi

    PHASE="$1"
    WORK_ID="$2"
    TITLE="$3"
    STATUS="$4"
    DOC_PATH="$5"
    WORK_DIR="$6"

    # 레거시 방식에서 WORK_DIR이 비어있을 때: registry.json에서 workId로 역해석
    if [ -z "$WORK_DIR" ] && [ -n "$WORK_ID" ] && [[ "$WORK_ID" =~ ^[0-9]{6}$ ]]; then
        _REG_FILE="${PROJECT_ROOT}/.workflow/registry.json"
        if [ -f "$_REG_FILE" ] && command -v python3 &>/dev/null; then
            WORK_DIR=$(WF_REG="$_REG_FILE" WF_WID="$WORK_ID" python3 -c "
import json, os
try:
    with open(os.environ['WF_REG'], 'r', encoding='utf-8') as f:
        data = json.load(f)
    wid = os.environ['WF_WID']
    for key, val in data.items():
        if key.endswith('-' + wid) and 'workDir' in val:
            print(val['workDir'])
            break
except Exception:
    pass
" 2>/dev/null || true)
        fi
    fi

    # 레거시 방식에서도 workDir 절대 경로 계산 (DONE 배너 Slack 호출에 사용)
    if [ -n "$WORK_DIR" ]; then
        if [[ "$WORK_DIR" == /* ]]; then
            _ABS_WORK_DIR="$WORK_DIR"
        else
            _ABS_WORK_DIR="${PROJECT_ROOT}/${WORK_DIR}"
        fi
    fi
fi

# 색상 코드 (ANSI)
RED='\033[0;31m'
BLUE='\033[0;34m'
GREEN='\033[0;32m'
PURPLE='\033[0;35m'
BOLD='\033[1m'
DIM='\033[2m'
RESET='\033[0m'
YELLOW='\033[0;33m'
GRAY='\033[0;90m'

# 단계별 색상
get_color() {
    case "$1" in
        INIT)   echo "$RED" ;;
        PLAN)   echo "$BLUE" ;;
        WORK)   echo "$GREEN" ;;
        REPORT) echo "$PURPLE" ;;
        DONE)   echo '\033[0;33m' ;;
        *)      echo '\033[0;37m' ;;
    esac
}

# 프로그레스 바: 현재 단계까지 채움, 나머지 빈칸
get_progress() {
    local phase="$1"
    case "$phase" in
        INIT)   echo "${RED}${BOLD}■${RESET}${GRAY}□□□${RESET}" ;;
        PLAN)   echo "${RED}■${BLUE}${BOLD}■${RESET}${GRAY}□□${RESET}" ;;
        WORK)   echo "${RED}■${BLUE}■${GREEN}${BOLD}■${RESET}${GRAY}□${RESET}" ;;
        REPORT) echo "${RED}■${BLUE}■${GREEN}■${PURPLE}${BOLD}■${RESET}" ;;
        DONE)   echo "${RED}■${BLUE}■${GREEN}■${PURPLE}■${RESET}" ;;
        *)      echo "${GRAY}□□□□${RESET}" ;;
    esac
}

# --- INIT 완료 배너 방어 로직 ---
# INIT phase의 완료 배너(status 지정)는 출력하지 않고 조기 종료
# 문서상 제거되었지만, LLM이 호출하더라도 출력이 없도록 방어
if [ "$PHASE" = "INIT" ] && [ -n "$STATUS" ]; then
    exit 0
fi

COLOR=$(get_color "$PHASE")
PROGRESS=$(get_progress "$PHASE")

# 배너 폭: 콘텐츠 표시 너비에 따라 동적 계산 (최소 60, 최대 100)
MIN_WIDTH=60
MAX_WIDTH=100

# 터미널 표시 너비 계산 (한글 등 wide 문자는 2칸 차지)
display_width() {
    python3 -c "
import unicodedata, sys
s = sys.argv[1]
print(sum(2 if unicodedata.east_asian_width(c) in ('W','F') else 1 for c in s))
" "$1" 2>/dev/null || echo "${#1}"
}

TITLE_DWIDTH=$(display_width "$TITLE")

# 콘텐츠 길이 계산 (프로그레스 4자 + 여백 + PHASE + workId + 구분자 + TITLE)
if [ "$WORK_ID" = "none" ]; then
    CONTENT_LEN=$(( ${#PHASE} + TITLE_DWIDTH + 10 ))
else
    CONTENT_LEN=$(( ${#PHASE} + ${#WORK_ID} + TITLE_DWIDTH + 13 ))
fi

WIDTH=$CONTENT_LEN
[ $WIDTH -lt $MIN_WIDTH ] && WIDTH=$MIN_WIDTH
[ $WIDTH -gt $MAX_WIDTH ] && WIDTH=$MAX_WIDTH

LINE=$(printf '─%.0s' $(seq 1 $WIDTH))

if [ "$PHASE" = "DONE" ]; then
    # 최종 완료 배너 (박스 없이 한 줄)
    echo ""
    echo -e "  ${PROGRESS}  ${YELLOW}${BOLD}DONE${RESET}  ${WORK_ID} · ${TITLE}  ${YELLOW}${BOLD}워크플로우 완료${RESET}"
    echo ""

    # --- Slack 완료 알림 (비동기, 비차단) ---
    if [ -n "$WORK_DIR" ]; then
        (
            _REPORT_PATH=""
            if [ -f "${_ABS_WORK_DIR}/report.md" ]; then
                _REPORT_PATH="${WORK_DIR}/report.md"
            fi
            bash "$SCRIPT_DIR/../slack/slack.sh" "$WORK_DIR" "완료" "$_REPORT_PATH" "" 2>/dev/null
        ) &
    fi
elif [ -z "$STATUS" ]; then
    # ─── 시작 배너 ───
    echo ""
    echo -e "${COLOR}┌${LINE}┐${RESET}"
    if [ "$WORK_ID" = "none" ]; then
        # INIT 시작: workId 없음, title에 command명
        echo -e "  ${PROGRESS}  ${COLOR}${BOLD}${PHASE}${RESET}  ${TITLE}"
    else
        echo -e "  ${PROGRESS}  ${COLOR}${BOLD}${PHASE}${RESET}  ${WORK_ID} · ${TITLE}"
    fi
    echo -e "${COLOR}└${LINE}┘${RESET}"
else
    # ─── 완료 배너 ───
    # DOC_PATH 자동 추론: 명시적 path가 없으면 phase별 기본 경로 사용
    if [ -z "$DOC_PATH" ] && [ -n "$WORK_DIR" ]; then
        case "$PHASE" in
            PLAN)   DOC_PATH="${WORK_DIR}/plan.md" ;;
            WORK)   DOC_PATH="${WORK_DIR}/work/" ;;
            REPORT) DOC_PATH="${WORK_DIR}/report.md" ;;
        esac
    fi
    if [ -n "$DOC_PATH" ]; then
        echo -e "${COLOR}  ✓ ${BOLD}${PHASE}${RESET}  ${DIM}${WORK_ID} · ${TITLE}${RESET}"
        echo -e "${COLOR}  ✓ ${DIM}${DOC_PATH}${RESET}"
    else
        echo -e "${COLOR}  ✓ ${BOLD}${PHASE}${RESET}  ${DIM}${WORK_ID} · ${TITLE}${RESET}"
    fi
    # 패딩: 의미 있는 텍스트로 AskUserQuestion UI 덮어쓰기 방지
    echo -e "${COLOR}  ✓ ${BOLD}${PHASE} DONE${RESET}"
fi
