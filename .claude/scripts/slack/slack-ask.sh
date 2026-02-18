#!/bin/bash
# AskUserQuestion 호출 시 Slack 알림 전송 스크립트
# PreToolUse Hook에서 호출됨 (stdin으로 JSON 입력 수신)
#
# 환경변수 (.claude.env에서 로드):
#   CLAUDE_CODE_SLACK_BOT_TOKEN - Slack Bot OAuth Token
#   CLAUDE_CODE_SLACK_CHANNEL_ID - Slack Channel ID
#
# 워크플로우 식별 방식 (활성 워크플로우 레지스트리 기반):
#   1. 전역 .workflow/registry.json 딕셔너리에서 활성 워크플로우 목록 조회
#   2. 활성 워크플로우 1개 -> 해당 워크플로우 선택
#   3. 복수 -> phase="PLAN" 인 워크플로우 필터링
#   4. PLAN 복수 -> 각 워크플로우의 status.json에서 가장 최근 updated_at인 워크플로우 선택
#   5. 식별된 워크플로우의 로컬 <workDir>/.context.json 읽어 메시지 구성
#   6. 식별 실패 시 기존 폴백 포맷 사용
#
# 에이전트별 색상 이모지:
#   로컬 .context.json의 agent 필드를 읽어 해당 에이전트의 이모지를 메시지 앞에 표시

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 공용 함수 라이브러리 로드
source "$SCRIPT_DIR/../_utils/slack-common.sh"

# .claude.env에서 환경변수 로드
if ! load_slack_env; then
    exit 0
fi

# stdin에서 JSON 읽기
INPUT=$(cat)

# tool_input에서 첫 번째 질문 추출 (공용 함수의 jq > python3 폴백 체인 사용)
QUESTION=$(echo "$INPUT" | extract_json_field \
    '.tool_input.questions[0].question // "N/A"' \
    "data.get('tool_input',{}).get('questions',[{}])[0].get('question','N/A')")

# tool_input에서 선택지(options) 추출 (label + description을 " | "로 연결)
OPTIONS_LINE=""
if command -v jq &>/dev/null; then
    OPTIONS_RAW=$(printf '%s' "$INPUT" | jq -r '[.tool_input.questions[0].options[]? | (.label // "") as $l | (.description // "") as $d | if $l != "" then (if $d != "" then "\($l) - \($d)" else $l end) else empty end] | if length > 0 then join(" | ") else empty end' 2>/dev/null)
elif command -v python3 &>/dev/null; then
    OPTIONS_RAW=$(printf '%s' "$INPUT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    opts = data.get('tool_input',{}).get('questions',[{}])[0].get('options',[])
    parts = []
    for o in opts:
        label = o.get('label','')
        desc = o.get('description','')
        if label:
            parts.append(f'{label} - {desc}' if desc else label)
    print(' | '.join(parts) if parts else '')
except:
    print('')
" 2>/dev/null)
fi
if [ -n "$OPTIONS_RAW" ]; then
    OPTIONS_LINE="\n- 선택지: ${OPTIONS_RAW}"
fi

# 활성 워크플로우 레지스트리에서 워크플로우 식별 및 메시지 구성
REGISTRY_FILE="$PROJECT_ROOT/.workflow/registry.json"
CONTEXT_LOADED=false
AGENT_EMOJI=""
CTX_PHASE=""

if [ -f "$REGISTRY_FILE" ]; then
    # 외부 Python 스크립트로 워크플로우 식별
    CONTEXT=$(python3 "$SCRIPT_DIR/../_utils/resolve-workflow.py" "$REGISTRY_FILE" "$PROJECT_ROOT" 2>/dev/null)

    if [ -n "$CONTEXT" ]; then
        CTX_TITLE=$(echo "$CONTEXT" | sed -n '1p')
        CTX_WORK_ID=$(echo "$CONTEXT" | sed -n '2p')
        CTX_WORK_NAME=$(echo "$CONTEXT" | sed -n '3p')
        CTX_COMMAND=$(echo "$CONTEXT" | sed -n '4p')
        CTX_AGENT=$(echo "$CONTEXT" | sed -n '5p')
        CTX_PHASE=$(echo "$CONTEXT" | sed -n '6p')
        AGENT_EMOJI=$(get_agent_emoji "$CTX_AGENT")
        CONTEXT_LOADED=true
    fi
fi

# 이모지 접두사 생성 (에이전트 정보가 있을 때만)
EMOJI_PREFIX=""
if [ -n "$AGENT_EMOJI" ]; then
    EMOJI_PREFIX="${AGENT_EMOJI} "
fi

# phase 정보 문자열 생성 (status.json에서 읽은 경우에만)
PHASE_LINE=""
if [ -n "$CTX_PHASE" ]; then
    PHASE_LINE="\n- 현재 단계: ${CTX_PHASE}"
fi

# Slack 메시지 구성
if [ "$CONTEXT_LOADED" = true ]; then
    # 통일 포맷 (slack.sh와 동일, 에이전트 이모지 포함, 보고서 링크 제외)
    MESSAGE="${EMOJI_PREFIX}*${CTX_TITLE}*\n- 작업ID: \`${CTX_WORK_ID}\`\n- 작업이름: ${CTX_WORK_NAME}\n- 명령어: \`${CTX_COMMAND}\`${PHASE_LINE}\n- 상태: 사용자 입력 대기 중\n- 질문: ${QUESTION}${OPTIONS_LINE}"
else
    # 폴백 포맷 (registry.json 없거나 워크플로우 식별 실패)
    MESSAGE=":bell: *사용자 입력 대기 중*\n- 질문: ${QUESTION}${OPTIONS_LINE}"
fi

# JSON payload 구성 + Slack 전송 (공용 함수 사용)
JSON_PAYLOAD=$(build_json_payload "$SLACK_CHANNEL_ID" "$MESSAGE")
send_slack_message "$JSON_PAYLOAD"

exit 0
