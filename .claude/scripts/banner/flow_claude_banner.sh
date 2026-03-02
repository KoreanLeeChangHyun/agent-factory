#!/usr/bin/env bash
# flow_claude_banner.sh - 워크플로우 시작/종료 배너 통합
#
# 사용법:
#   flow-claude start <command>
#   flow-claude end <registryKey>
#
# 예시:
#   flow-claude start implement
#   flow-claude end 20260228-133000

set -euo pipefail

SUBCMD="${1:-}"

if [[ -z "$SUBCMD" ]]; then
    echo "사용법: flow-claude <start|end> ..." >&2
    exit 0
fi

# ═══════════════════════════════════════════════════════
# start: flow-claude start <command> <mode>
# ═══════════════════════════════════════════════════════
if [[ "$SUBCMD" == "start" ]]; then
    COMMAND="${2:-}"

    if [[ -z "$COMMAND" ]]; then
        echo "사용법: flow-claude start <command>" >&2
        exit 0
    fi

    # ─── 자체 색상 정의 (Claude 브랜드 Peach #DE7356) ───
    C_ORANGE='\033[38;2;222;115;86m'
    C_WHITE='\033[0;37m'
    C_BOLD='\033[1m'
    C_RESET='\033[0m'

    INNER_WIDTH=60
    BORDER=$(printf '═%.0s' $(seq 1 $INNER_WIDTH))

    DATESTAMP=$(TZ='Asia/Seoul' date '+%Y년 %-m월 %-d일')
    TITLE_LEFT="  Claude Code - Workflow"
    TITLE_RIGHT="${DATESTAMP}  "

    HOUR=$(TZ='Asia/Seoul' date '+%-H')
    MINUTE=$(TZ='Asia/Seoul' date '+%-M')
    if [[ $HOUR -lt 12 ]]; then
        AMPM="오전"
        [[ $HOUR -eq 0 ]] && HOUR=12
    else
        AMPM="오후"
        [[ $HOUR -gt 12 ]] && HOUR=$((HOUR - 12))
    fi
    TIMESTAMP="${AMPM} ${HOUR}시 ${MINUTE}분 KST"
    INFO_LEFT="  ▶ ${COMMAND}"
    INFO_RIGHT="${TIMESTAMP}  "

    # ─── 한글 표시 폭 계산 (4개 문자열을 단일 Python 호출로 처리) ───
    read -r TITLE_LEFT_W TITLE_RIGHT_W INFO_LEFT_W INFO_RIGHT_W < <(python3 -c "
import unicodedata
def w(s):
    return len(s) + sum(1 for c in s if unicodedata.east_asian_width(c) in ('W','F'))
import sys
strs = sys.argv[1:]
print(' '.join(str(w(s)) for s in strs))
" "$TITLE_LEFT" "$TITLE_RIGHT" "$INFO_LEFT" "$INFO_RIGHT" 2>/dev/null || echo "0 0 0 0")

    TITLE_PAD=$((INNER_WIDTH - TITLE_LEFT_W - TITLE_RIGHT_W))
    TITLE_SPACES=$(printf '%*s' "$TITLE_PAD" '')
    INFO_PAD=$((INNER_WIDTH - INFO_LEFT_W - INFO_RIGHT_W))
    INFO_SPACES=$(printf '%*s' "$INFO_PAD" '')

    echo -e "${C_ORANGE}╔${BORDER}╗${C_RESET}"
    echo -e "${C_ORANGE}║${C_RESET}  ${C_BOLD}${C_ORANGE}Claude Code${C_RESET} - Workflow${TITLE_SPACES}${C_WHITE}${TITLE_RIGHT}${C_RESET}${C_ORANGE}║${C_RESET}"
    echo -e "${C_ORANGE}║${C_RESET}  ${C_ORANGE}▶${C_RESET} ${COMMAND}${INFO_SPACES}${C_WHITE}${INFO_RIGHT}${C_RESET}${C_ORANGE}║${C_RESET}"
    echo -e "${C_ORANGE}╚${BORDER}╝${C_RESET}"
    exit 0
fi

# ═══════════════════════════════════════════════════════
# end: flow-claude end <registryKey>
# ═══════════════════════════════════════════════════════
if [[ "$SUBCMD" == "end" ]]; then
    REGISTRY_KEY="${2:-}"

    if [[ -z "$REGISTRY_KEY" ]]; then
        echo "사용법: flow-claude end <registryKey>" >&2
        exit 0
    fi

    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
    source "$SCRIPT_DIR/../data/colors.sh"

    # ─── registryKey → context.json 해석 ───
    WORK_DIR=""
    WORK_ID=""
    TITLE=""
    COMMAND=""

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

    if [[ -n "$WORK_DIR" ]]; then
        ABS_WORK_DIR="$PROJECT_ROOT/$WORK_DIR"
        CTX_FILE="$ABS_WORK_DIR/.context.json"
        if [[ -f "$CTX_FILE" ]]; then
            eval "$(python3 -c "
import json
try:
    d=json.load(open('$CTX_FILE'))
    wid=d.get('workId','').replace(\"'\",\"\")
    ttl=d.get('title','').replace(\"'\",\"\")
    cmd=d.get('command','').replace(\"'\",\"\")
    print(f\"WORK_ID='{wid}'\")
    print(f\"TITLE='{ttl}'\")
    print(f\"COMMAND='{cmd}'\")
except: pass
" 2>/dev/null || true)"
        fi
    fi

    WORK_ID="${WORK_ID:-none}"
    TITLE="${TITLE:-unknown}"

    CMD_LABEL=""
    if [[ -n "$COMMAND" ]]; then
        CMD_LABEL=" ${C_DIM}(${COMMAND})${C_RESET}"
    fi

    BORDER=$(printf '═%.0s' $(seq 1 62))
    echo -e "${C_CLAUDE}║${C_RESET} ${C_YELLOW}${C_BOLD}[OK]${C_RESET} ${C_DIM}${WORK_ID}${C_RESET} · ${TITLE}${CMD_LABEL}"
    echo -e "${C_CLAUDE}${BORDER}${C_RESET}"

    # ─── Slack 완료 알림 (비동기, 비차단) ───
    if [[ -n "$WORK_DIR" ]]; then
        REPORT_PATH=""
        if [[ -f "$PROJECT_ROOT/$WORK_DIR/report.md" ]]; then
            REPORT_PATH="$WORK_DIR/report.md"
        fi
        SLACK_PY="$SCRIPT_DIR/../slack/slack_notify.py"
        if [[ -f "$SLACK_PY" ]]; then
            python3 "$SLACK_PY" "$WORK_DIR" "완료" "$REPORT_PATH" "" &>/dev/null &
        fi
    fi
    exit 0
fi

echo "사용법: flow-claude <start|end> ..." >&2
