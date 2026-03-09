#!/usr/bin/env bash
# flow_step_banner.sh - 워크플로우 단계 배너 출력
#
# 사용법:
#   flow-step start <registryKey>              # Step 시작 배너 (2줄)
#   flow-step end   <registryKey>              # Step 완료 (3줄: 진행+링크+[ASK])
#   flow-step end   <registryKey> <label>      # Step 완료 (3줄: 진행+링크+[OK])
#
# 예시:
#   flow-step start 20260301-061849
#   flow-step end   20260301-061849              # [ASK] 모드
#   flow-step end   20260301-061849 planSubmit   # [OK] 모드

set -euo pipefail

# ─── 공통 색상/유틸리티 로드 ───
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../data/colors.sh"

# ─── 한글 표시 폭 계산 ───
display_width() {
    local str="$1"
    python3 -c "
import unicodedata, sys
s = sys.argv[1]
print(sum(2 if unicodedata.east_asian_width(c) in ('W', 'F') else 1 for c in s))
" "$str" 2>/dev/null || echo "${#str}"
}

# ─── 한국어 시간 포맷 ───
get_kr_timestamp() {
    local HOUR MINUTE AMPM
    HOUR=$(TZ='Asia/Seoul' date '+%-H')
    MINUTE=$(TZ='Asia/Seoul' date '+%-M')
    if [[ $HOUR -lt 12 ]]; then
        AMPM="오전"
        [[ $HOUR -eq 0 ]] && HOUR=12
    else
        AMPM="오후"
        [[ $HOUR -gt 12 ]] && HOUR=$((HOUR - 12))
    fi
    echo "${AMPM} ${HOUR}시 ${MINUTE}분 KST"
}

# ─── 진행 표시 ───
get_progress() {
    local STEP="$1" ICON="$2"
    case "$STEP" in
        PLAN)     echo "${C_BLUE}${C_BOLD}${ICON}${C_RESET} ${C_GRAY}○ ○${C_RESET}" ;;
        WORK)     echo "${C_BLUE}${ICON}${C_RESET} ${C_GREEN}${C_BOLD}${ICON}${C_RESET} ${C_GRAY}○${C_RESET}" ;;
        REPORT)   echo "${C_BLUE}${ICON}${C_RESET} ${C_GREEN}${ICON}${C_RESET} ${C_PURPLE}${C_BOLD}${ICON}${C_RESET}" ;;
        DONE)     echo "${C_BLUE}${ICON}${C_RESET} ${C_GREEN}${ICON}${C_RESET} ${C_YELLOW}${C_BOLD}${ICON}${C_RESET}" ;;
        *)        echo "${C_GRAY}○ ○ ○${C_RESET}" ;;
    esac
}

# ─── registryKey → 현재 phase 조회 ───
get_current_phase() {
    local REGISTRY_KEY="$1"
    REGISTRY_KEY="$REGISTRY_KEY" SCRIPT_DIR="$SCRIPT_DIR" python3 -c "
import os, sys
sys.path.insert(0, os.path.normpath(os.path.join(os.environ['SCRIPT_DIR'], '..')))
from common import resolve_abs_work_dir, load_json_file, resolve_project_root
root = resolve_project_root()
wd = resolve_abs_work_dir(os.environ['REGISTRY_KEY'], root)
status = load_json_file(os.path.join(wd, 'status.json'))
print((status.get('step') or status.get('phase', 'NONE')) if isinstance(status, dict) else 'NONE')
" 2>/dev/null || echo "NONE"
}

# ─── workflow.log 이벤트 기록 ───
_log_event() {
    local REGISTRY_KEY="$1" LEVEL="$2" MESSAGE="$3"
    REGISTRY_KEY="$REGISTRY_KEY" SCRIPT_DIR="$SCRIPT_DIR" LEVEL="$LEVEL" MESSAGE="$MESSAGE" python3 -c "
import os, sys
sys.path.insert(0, os.path.normpath(os.path.join(os.environ['SCRIPT_DIR'], '..')))
from common import resolve_abs_work_dir, resolve_project_root
from datetime import datetime, timezone, timedelta
try:
    root = resolve_project_root()
    wd = resolve_abs_work_dir(os.environ['REGISTRY_KEY'], root)
    kst = timezone(timedelta(hours=9))
    ts = datetime.now(kst).strftime('%Y-%m-%dT%H:%M:%S')
    log_path = os.path.join(wd, 'workflow.log')
    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(f'[{ts}] [{os.environ[\"LEVEL\"]}] {os.environ[\"MESSAGE\"]}\n')
except Exception:
    pass
" 2>/dev/null || true
}

# ─── registryKey → 산출물 상대경로 해석 ───
get_artifact_path() {
    local STEP="$1" REGISTRY_KEY="$2"
    REGISTRY_KEY="$REGISTRY_KEY" STEP="$STEP" SCRIPT_DIR="$SCRIPT_DIR" python3 -c "
import os, sys
sys.path.insert(0, os.path.normpath(os.path.join(os.environ['SCRIPT_DIR'], '..')))
from common import resolve_abs_work_dir, resolve_project_root
root = resolve_project_root()
wd = resolve_abs_work_dir(os.environ['REGISTRY_KEY'], root)
rel = os.path.relpath(wd, root)
artifact = {'PLAN': 'plan.md', 'WORK': 'work', 'REPORT': 'report.md'}.get(os.environ['STEP'], '')
if artifact:
    full = os.path.join(wd, artifact)
    if os.path.isfile(full) or os.path.isdir(full):
        print(os.path.join(rel, artifact))
" 2>/dev/null || echo ""
}

# ─── 단계 설명 ───
get_step_desc() {
    case "$1" in
        PLAN)     echo "계획 수립" ;;
        WORK)     echo "작업 실행" ;;
        REPORT)   echo "보고서 작성" ;;
        *)        echo "" ;;
    esac
}

# ─── 서브커맨드 파싱 ───
SUBCMD="${1:-}"

if [[ -z "$SUBCMD" ]]; then
    echo "사용법: flow-step <start|end> <registryKey> [label]" >&2
    exit 0
fi

# ═══════════════════════════════════════════════════════
# start: flow-step start <registryKey>
# ═══════════════════════════════════════════════════════
if [[ "$SUBCMD" == "start" ]]; then
    REGISTRY_KEY="${2:-}"
    if [[ -z "$REGISTRY_KEY" ]]; then
        echo "사용법: flow-step start <registryKey>" >&2
        exit 0
    fi

    STEP=$(get_current_phase "$REGISTRY_KEY")
    COLOR=$(get_color "$STEP")
    PROGRESS=$(get_progress "$STEP" "●")
    DATESTAMP=$(TZ='Asia/Seoul' date '+%Y년 %-m월 %-d일')
    TIMESTAMP=$(get_kr_timestamp)
    DESC=$(get_step_desc "$STEP")

    BORDER=$(printf '═%.0s' $(seq 1 $BANNER_WIDTH))

    # Line 1: [● ● ○]  STEP                    2026년 3월 1일  ║
    LINE1_LEFT="  [X X X]  ${STEP}"
    LINE1_RIGHT="${DATESTAMP}  "
    LINE1_LEFT_W=$(( 2 + 7 + 2 + ${#STEP} ))  # "  " + "[X X X]" + "  " + STEP
    LINE1_RIGHT_W=$(display_width "$LINE1_RIGHT")
    LINE1_PAD=$(( BANNER_WIDTH - LINE1_LEFT_W - LINE1_RIGHT_W ))
    LINE1_SPACES=$(printf '%*s' "$LINE1_PAD" '')

    # Line 2: ▶ 설명                          오후 7시 13분 KST  ║
    LINE2_LEFT="  ▶ ${DESC}"
    LINE2_RIGHT="${TIMESTAMP}  "
    LINE2_LEFT_W=$(display_width "$LINE2_LEFT")
    LINE2_RIGHT_W=$(display_width "$LINE2_RIGHT")
    LINE2_PAD=$(( BANNER_WIDTH - LINE2_LEFT_W - LINE2_RIGHT_W ))
    LINE2_SPACES=$(printf '%*s' "$LINE2_PAD" '')

    echo -e "${C_CLAUDE}╔${BORDER}╗${C_RESET}"
    echo -e "${C_CLAUDE}║${C_RESET}  ${C_CLAUDE}[${C_RESET}${PROGRESS}${C_CLAUDE}]${C_RESET}  ${COLOR}${C_BOLD}${STEP}${C_RESET}${LINE1_SPACES}${C_WHITE}${LINE1_RIGHT}${C_RESET}${C_CLAUDE}║${C_RESET}"
    echo -e "${C_CLAUDE}║${C_RESET}  ${C_CLAUDE}▶${C_RESET} ${DESC}${LINE2_SPACES}${C_WHITE}${LINE2_RIGHT}${C_RESET}${C_CLAUDE}║${C_RESET}"
    echo -e "${C_CLAUDE}╚${BORDER}╝${C_RESET}"
    _log_event "$REGISTRY_KEY" "INFO" "STEP_START: ${STEP}" || true
    exit 0
fi

# ═══════════════════════════════════════════════════════
# end: flow-step end <registryKey> [label]
# ═══════════════════════════════════════════════════════
if [[ "$SUBCMD" == "end" ]]; then
    REGISTRY_KEY="${2:-}"
    LABEL="${3:-}"
    if [[ -z "$REGISTRY_KEY" ]]; then
        echo "사용법: flow-step end <registryKey> [label]" >&2
        exit 0
    fi

    STEP=$(get_current_phase "$REGISTRY_KEY")
    COLOR=$(get_color "$STEP")
    PROGRESS=$(get_progress "$STEP" "●")
    TIMESTAMP=$(get_kr_timestamp)

    echo -e "${C_CLAUDE}║${C_RESET} ${C_CLAUDE}[${C_RESET}${PROGRESS}${C_CLAUDE}]${C_RESET}  ${COLOR}${C_BOLD}${STEP}${C_RESET}  ${C_DIM}- ${TIMESTAMP}${C_RESET}"

    ARTIFACT_PATH=$(get_artifact_path "$STEP" "$REGISTRY_KEY")
    if [[ -n "$ARTIFACT_PATH" ]]; then
        echo -e "${C_CLAUDE}║${C_RESET} ${C_DIM}${ARTIFACT_PATH}${C_RESET}"
    fi

    if [[ -n "$LABEL" ]]; then
        echo -e "${C_CLAUDE}║${C_RESET} ${C_YELLOW}${C_BOLD}[OK]${C_RESET} ${C_DIM}${LABEL}${C_RESET}"
    else
        echo -e "${C_CLAUDE}║ [ASK]${C_RESET} ${C_DIM}AskUserQuestion${C_RESET}"
    fi

    _LOG_MSG="STEP_END: ${STEP} label=${LABEL:-ASK}"
    _log_event "$REGISTRY_KEY" "INFO" "$_LOG_MSG" || true
    if [[ -n "$ARTIFACT_PATH" ]]; then
        _log_event "$REGISTRY_KEY" "INFO" "ARTIFACT: ${ARTIFACT_PATH}" || true
    fi
    exit 0
fi

echo "사용법: flow-step <start|end> <registryKey> [label]" >&2
