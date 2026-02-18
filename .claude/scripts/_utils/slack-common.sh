#!/bin/bash
# Slack 공용 함수 라이브러리
# slack.sh, slack-ask.sh에서 source로 로드하여 사용
#
# 제공 함수:
#   load_slack_env       - .claude.env에서 CLAUDE_CODE_SLACK_BOT_TOKEN, CLAUDE_CODE_SLACK_CHANNEL_ID 로드
#   get_agent_emoji      - 에이전트별 Slack 이모지 매핑
#   extract_json_field   - JSON에서 필드 추출 (jq > python3 2단계 폴백)
#   build_json_payload   - JSON payload 구성 (jq > python3 > sed 3단계 폴백)
#   send_slack_message   - curl로 Slack API 호출 + 응답 검증
#   log_info             - stderr로 정보 로그 출력
#   log_warn             - stderr로 경고 로그 출력

# 호출자가 SCRIPT_DIR을 설정하지 않은 경우 기본값
if [ -z "$SLACK_COMMON_DIR" ]; then
    SLACK_COMMON_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi

# PROJECT_ROOT 계산 (_utils -> scripts -> .claude -> project root)
if [ -z "$PROJECT_ROOT" ]; then
    PROJECT_ROOT="$(cd "$SLACK_COMMON_DIR/../../.." && pwd)"
fi

# 공통 env 파싱 유틸리티 로드 (read_env, set_env)
ENV_FILE="${ENV_FILE:-$PROJECT_ROOT/.claude.env}"
source "$SLACK_COMMON_DIR/env-utils.sh"

# ──────────────────────────────────────────────
# 로그 함수 (모두 stderr로 출력)
# ──────────────────────────────────────────────

log_info() {
    echo "[OK] $*" >&2
}

log_warn() {
    echo "[WARN] $*" >&2
}

# ──────────────────────────────────────────────
# .claude.env에서 Slack 환경변수 로드
# 설정 후 SLACK_BOT_TOKEN, SLACK_CHANNEL_ID 전역변수 사용 가능
# 반환값: 0=성공, 1=환경변수 누락
# ──────────────────────────────────────────────

load_slack_env() {
    SLACK_BOT_TOKEN=$(read_env "CLAUDE_CODE_SLACK_BOT_TOKEN")
    SLACK_CHANNEL_ID=$(read_env "CLAUDE_CODE_SLACK_CHANNEL_ID")

    if [ -z "$SLACK_BOT_TOKEN" ] || [ -z "$SLACK_CHANNEL_ID" ]; then
        log_warn "CLAUDE_CODE_SLACK_BOT_TOKEN 또는 CLAUDE_CODE_SLACK_CHANNEL_ID가 설정되지 않았습니다. Slack 전송을 건너뜁니다."
        return 1
    fi

    return 0
}

# ──────────────────────────────────────────────
# 에이전트별 Slack 이모지 매핑
# 인자: $1 = 에이전트 이름 (init|planner|worker|reporter)
# 출력: 이모지 문자열 (매칭 없으면 빈 문자열)
# ──────────────────────────────────────────────

get_agent_emoji() {
    local agent_name="$1"
    case "$agent_name" in
        init)     echo ":large_orange_circle:" ;;
        planner)  echo ":large_blue_circle:" ;;
        worker)   echo ":large_green_circle:" ;;
        reporter) echo ":purple_circle:" ;;
        *)        echo "" ;;
    esac
}

# ──────────────────────────────────────────────
# JSON 필드 추출 (2단계 폴백 체인)
# 1순위: jq (정확한 JSON 파싱)
# 2순위: python3 json 모듈
#
# 인자: $1 = jq 필터식 (예: '.tool_input.questions[0].question // "N/A"')
#       $2 = python3 추출 코드 (예: "data.get('tool_input',{}).get('questions',[{}])[0].get('question','N/A')")
# stdin: JSON 입력
# 출력: 추출된 값 (stdout)
# ──────────────────────────────────────────────

extract_json_field() {
    local jq_filter="$1"
    local py_expr="$2"
    local input
    input=$(cat)

    if command -v jq &>/dev/null; then
        # 1순위: jq
        local result
        result=$(printf '%s' "$input" | jq -r "$jq_filter" 2>/dev/null)
        if [ $? -eq 0 ] && [ -n "$result" ] && [ "$result" != "null" ]; then
            echo "$result"
            return 0
        fi
    fi

    if command -v python3 &>/dev/null; then
        # 2순위: python3
        printf '%s' "$input" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    result = $py_expr
    print(result if result is not None else 'N/A')
except:
    print('N/A')
" 2>/dev/null
        return 0
    fi

    echo "N/A"
    return 1
}

# ──────────────────────────────────────────────
# JSON payload 구성 (3단계 폴백 체인)
# 1순위: jq (완전한 이스케이프 보장)
# 2순위: python3 json.dumps (jq 미설치 시)
# 3순위: sed 수동 이스케이프 (jq, python3 모두 미설치 시)
#
# 인자: $1 = channel, $2 = text
# 출력: JSON 문자열 (stdout)
# ──────────────────────────────────────────────

build_json_payload() {
    local channel="$1"
    local text="$2"

    # 리터럴 \n을 실제 줄바꿈(0x0a)으로 변환
    # bash 큰따옴표 내 \n은 리터럴 2문자(0x5C 0x6E)이므로 printf '%b'로 실제 줄바꿈으로 변환
    # jq --arg, python3 json.dumps가 실제 줄바꿈을 올바른 JSON \n으로 이스케이프하도록 보장
    # 주의: printf '%b'는 \t, \\ 등도 해석하나 현재 메시지 패턴에서 부작용 없음
    text=$(printf '%b' "$text")

    if command -v jq &>/dev/null; then
        # 1순위: jq
        jq -n \
            --arg channel "$channel" \
            --arg text "$text" \
            '{channel: $channel, text: $text, mrkdwn: true}'
    elif command -v python3 &>/dev/null; then
        # 2순위: python3 json.dumps
        python3 -c "
import json, sys
print(json.dumps({
    'channel': sys.argv[1],
    'text': sys.argv[2],
    'mrkdwn': True
}))
" "$channel" "$text" 2>/dev/null
    else
        # 3순위: sed 수동 이스케이프
        local escaped_text
        escaped_text=$(printf '%s' "$text" | sed 's/\\/\\\\/g; s/"/\\"/g; s/\t/\\t/g; s/$/\\n/g' | tr -d '\n' | sed 's/\\n$//')
        printf '%s\n' "{\"channel\":\"$channel\",\"text\":\"$escaped_text\",\"mrkdwn\":true}"
    fi
}

# ──────────────────────────────────────────────
# Slack API로 메시지 전송 + 응답 검증
# 인자: $1 = JSON payload 문자열
# 반환값: 0=성공, 1=실패
# ──────────────────────────────────────────────

send_slack_message() {
    local json_payload="$1"

    local response
    response=$(curl -s -X POST "https://slack.com/api/chat.postMessage" \
        -H "Authorization: Bearer $SLACK_BOT_TOKEN" \
        -H "Content-Type: application/json" \
        -d "$json_payload" 2>/dev/null)

    # 응답 검증: jq > python3 > grep 3단계 폴백
    local is_ok=""
    if command -v jq &>/dev/null; then
        # 1순위: jq
        is_ok=$(echo "$response" | jq -r '.ok' 2>/dev/null)
        if [ "$is_ok" = "true" ]; then
            log_info "Slack 메시지 전송 성공"
            return 0
        fi
    elif command -v python3 &>/dev/null; then
        # 2순위: python3
        is_ok=$(echo "$response" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print('true' if data.get('ok') else 'false')
except:
    print('false')
" 2>/dev/null)
        if [ "$is_ok" = "true" ]; then
            log_info "Slack 메시지 전송 성공"
            return 0
        fi
    else
        # 3순위: grep 폴백
        is_ok=$(echo "$response" | grep -o '"ok" *: *true')
        if [ -n "$is_ok" ]; then
            log_info "Slack 메시지 전송 성공"
            return 0
        fi
    fi

    log_warn "Slack 메시지 전송 실패: $response"
    return 1
}
