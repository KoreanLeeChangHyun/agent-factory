#!/usr/bin/env bash
# show_state.sh - 워크플로우 상태 전이 시각화
#
# 사용법:
#   show_state.sh <registryKey>
#
# 예시:
#   show_state.sh 20260219-042258
#
# status.json의 마지막 전이를 "FROM -> TO" + 타임스탬프 형식으로 색상 출력

set -euo pipefail

# ─── 인자 파싱 ───
REGISTRY_KEY="${1:-}"

if [[ -z "$REGISTRY_KEY" ]]; then
    echo "[WARN] show_state.sh: registryKey 인자가 필요합니다" >&2
    exit 0
fi

# ─── 프로젝트 루트 해석 ───
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"

# ─── registry.json에서 workDir 조회 ───
REGISTRY_FILE="$PROJECT_ROOT/.workflow/registry.json"
WORK_DIR=""

if [[ -f "$REGISTRY_FILE" ]]; then
    WORK_DIR=$(python3 -c "
import json
try:
    d=json.load(open('$REGISTRY_FILE'))
    print(d.get('$REGISTRY_KEY',{}).get('workDir',''))
except: pass
" 2>/dev/null || true)
fi

if [[ -z "$WORK_DIR" ]]; then
    echo "[WARN] show_state.sh: registryKey '$REGISTRY_KEY'에 대한 workDir을 찾을 수 없습니다" >&2
    exit 0
fi

# ─── status.json 경로 해석 ───
STATUS_FILE="$PROJECT_ROOT/$WORK_DIR/status.json"

if [[ ! -f "$STATUS_FILE" ]]; then
    echo "[WARN] show_state.sh: status.json을 찾을 수 없습니다: $STATUS_FILE" >&2
    exit 0
fi

# ─── 마지막 전이 추출 ───
TRANSITION=$(python3 -c "
import json, sys
try:
    d=json.load(open('$STATUS_FILE'))
    ts=d.get('transitions',[])
    if not ts:
        sys.exit(1)
    last=ts[-1]
    print(last.get('from',''))
    print(last.get('to',''))
    print(last.get('at',''))
except:
    sys.exit(1)
" 2>/dev/null) || {
    echo "[WARN] show_state.sh: transitions가 비어있거나 파싱 실패" >&2
    exit 0
}

FROM=$(echo "$TRANSITION" | sed -n '1p')
TO=$(echo "$TRANSITION" | sed -n '2p')
AT=$(echo "$TRANSITION" | sed -n '3p')

if [[ -z "$FROM" || -z "$TO" ]]; then
    echo "[WARN] show_state.sh: 전이 정보가 불완전합니다" >&2
    exit 0
fi

# ─── 타임스탬프에서 HH:MM:SS 추출 ───
TIMESTAMP=$(echo "$AT" | python3 -c "
import sys
s=sys.stdin.read().strip()
# ISO 8601: 2026-02-20T02:57:24+09:00 -> T 뒤의 HH:MM:SS
if 'T' in s:
    t=s.split('T')[1][:8]
    print(t)
else:
    print(s)
" 2>/dev/null || echo "$AT")

# ─── ANSI 색상 코드 ───
C_RED='\033[0;31m'
C_BLUE='\033[0;34m'
C_GREEN='\033[0;32m'
C_PURPLE='\033[0;35m'
C_YELLOW='\033[0;33m'
C_GRAY='\033[0;90m'
C_DIM='\033[2m'
C_RESET='\033[0m'

# ─── phase별 색상 매핑 ───
get_color() {
    case "$1" in
        INIT)                       echo "$C_RED" ;;
        PLAN)                       echo "$C_BLUE" ;;
        WORK)                       echo "$C_GREEN" ;;
        REPORT)                     echo "$C_PURPLE" ;;
        DONE|COMPLETED)             echo "$C_YELLOW" ;;
        CANCELLED|STALE|FAILED)     echo "$C_GRAY" ;;
        *)                          echo "$C_GRAY" ;;
    esac
}

COLOR_FROM=$(get_color "$FROM")
COLOR_TO=$(get_color "$TO")

# ─── 출력 ───
echo -e "  \xe2\x9f\xab ${COLOR_FROM}${FROM}${C_RESET} \xe2\x86\x92 ${COLOR_TO}${TO}${C_RESET}  ${C_DIM}${TIMESTAMP}${C_RESET}"
