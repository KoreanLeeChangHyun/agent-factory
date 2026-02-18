#!/bin/bash
# Slack 메시지 전송 스크립트
#
# 새 시그니처 (workDir 기반):
#   ./slack.sh <workDir> <상태> [보고서경로] [에이전트]
#   - workDir이 .workflow/ 또는 절대경로(/)로 시작하면 새 방식으로 감지
#   - workDir 형식: .workflow/YYYYMMDD-HHMMSS/<workName>/<command>
#     (예: .workflow/20260208-133900/디렉터리-구조-변경/implement)
#   - .context.json에서 title, workId, workName, command 자동 읽기
#
# 기존 시그니처 (하위 호환):
#   ./slack.sh <작업제목> <작업ID> <작업이름> <명령어> <상태> [보고서경로] [에이전트]
#
# 환경변수 (.claude.env에서 로드):
#   CLAUDE_CODE_SLACK_BOT_TOKEN - Slack Bot OAuth Token
#   CLAUDE_CODE_SLACK_CHANNEL_ID - Slack Channel ID
#
# 에이전트별 색상 이모지:
#   agent 인자를 전달받으면 해당 값으로 이모지 결정
#   agent 인자가 없으면 이모지 없이 기존 포맷 유지

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 공용 함수 라이브러리 로드
source "$SCRIPT_DIR/../_utils/slack-common.sh"

# 환경변수 로드 (실패 시 조용히 종료)
if ! load_slack_env; then
    exit 0
fi

# --- 이중 시그니처 감지 ---
# 1번째 인자가 .workflow/ 또는 절대경로(/)로 시작하면 새 방식 (workDir 기반)
if [[ "$1" == .workflow/* ]] || [[ "$1" == /* ]]; then
    # 새 방식: slack.sh <workDir> <상태> [보고서경로] [에이전트]
    if [ $# -lt 2 ]; then
        log_warn "사용법: $0 <workDir> <상태> [보고서경로] [에이전트]"
        exit 1
    fi

    WORK_DIR="$1"
    STATUS="$2"
    REPORT_PATH="$3"
    AGENT="$4"

    # workDir 절대 경로 계산
    if [[ "$WORK_DIR" = /* ]]; then
        _ABS_WORK_DIR="$WORK_DIR"
    else
        _ABS_WORK_DIR="${PROJECT_ROOT}/${WORK_DIR}"
    fi

    # .context.json 읽기
    _CONTEXT_FILE="${_ABS_WORK_DIR}/.context.json"
    if [ ! -f "$_CONTEXT_FILE" ]; then
        log_warn ".context.json을 찾을 수 없습니다: $_CONTEXT_FILE"
        exit 0
    fi

    # .context.json에서 필드 추출 (jq > python3 폴백)
    TITLE=""
    WORK_ID=""
    WORK_NAME=""
    COMMAND=""

    if command -v jq &>/dev/null; then
        TITLE=$(jq -r '.title // ""' "$_CONTEXT_FILE" 2>/dev/null)
        WORK_ID=$(jq -r '.workId // ""' "$_CONTEXT_FILE" 2>/dev/null)
        WORK_NAME=$(jq -r '.workName // ""' "$_CONTEXT_FILE" 2>/dev/null)
        COMMAND=$(jq -r '.command // ""' "$_CONTEXT_FILE" 2>/dev/null)
    elif command -v python3 &>/dev/null; then
        TITLE=$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(d.get('title',''))" "$_CONTEXT_FILE" 2>/dev/null)
        WORK_ID=$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(d.get('workId',''))" "$_CONTEXT_FILE" 2>/dev/null)
        WORK_NAME=$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(d.get('workName',''))" "$_CONTEXT_FILE" 2>/dev/null)
        COMMAND=$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(d.get('command',''))" "$_CONTEXT_FILE" 2>/dev/null)
    else
        log_warn ".context.json 파싱 도구 없음 (jq, python3 모두 미설치)"
        exit 0
    fi

    # 필수 필드 폴백
    [ -z "$TITLE" ] && TITLE="unknown"
    [ -z "$WORK_ID" ] && WORK_ID="none"
    [ -z "$WORK_NAME" ] && WORK_NAME="$TITLE"
    [ -z "$COMMAND" ] && COMMAND="unknown"

    # workDir에서 YYYYMMDD-HHMMSS 식별자 추출
    # 중첩 구조: .workflow/YYYYMMDD-HHMMSS/<workName>/<command> -> 3단계 상위 basename 사용
    # 레거시 플랫 구조: .workflow/YYYYMMDD-HHMMSS -> basename 그대로 사용
    _BASENAME=$(basename "$_ABS_WORK_DIR")
    if [[ "$_BASENAME" =~ ^[0-9]{8}-[0-9]{6}$ ]]; then
        # 레거시 플랫 구조: basename이 YYYYMMDD-HHMMSS 형식
        WORK_ID="$_BASENAME"
    else
        # 중첩 구조: 3단계 상위 디렉토리명 확인 (command -> workName -> YYYYMMDD-HHMMSS)
        _GRANDPARENT=$(basename "$(dirname "$(dirname "$_ABS_WORK_DIR")")")
        if [[ "$_GRANDPARENT" =~ ^[0-9]{8}-[0-9]{6}$ ]]; then
            WORK_ID="$_GRANDPARENT"
        else
            # 최종 폴백: .context.json의 workId 사용
            _DATE_PREFIX=$(echo "$_BASENAME" | grep -oP '^\d{8}' | head -1)
            if [ -n "$_DATE_PREFIX" ]; then
                WORK_ID="${_DATE_PREFIX}-${WORK_ID}"
            fi
        fi
    fi
else
    # 기존 방식: slack.sh <작업제목> <작업ID> <작업이름> <명령어> <상태> [보고서경로] [에이전트]
    if [ $# -lt 5 ]; then
        log_warn "사용법: $0 <작업제목> <작업ID> <작업이름> <명령어> <상태> [보고서경로] [에이전트]"
        exit 1
    fi

    TITLE="$1"
    WORK_ID="$2"
    WORK_NAME="$3"
    COMMAND="$4"
    STATUS="$5"
    REPORT_PATH="$6"
    AGENT="$7"
fi

# 에이전트 이모지 결정: agent 인자로 전달된 값 사용
AGENT_EMOJI=""
if [ -n "$AGENT" ]; then
    AGENT_EMOJI=$(get_agent_emoji "$AGENT")
fi

# 이모지 접두사 생성 (에이전트 정보가 있을 때만)
EMOJI_PREFIX=""
if [ -n "$AGENT_EMOJI" ]; then
    EMOJI_PREFIX="${AGENT_EMOJI} "
fi

# 보고서 vscode:// 링크 생성
REPORT_LINK=""
if [ -n "$REPORT_PATH" ]; then
    if [[ "$REPORT_PATH" = /* ]]; then
        ABS_REPORT_PATH="$REPORT_PATH"
    else
        ABS_REPORT_PATH="${PROJECT_ROOT}/${REPORT_PATH}"
    fi
    # URI percent-encoding (한글, 공백 등 특수문자 대응, python3 미설치 시 원본 경로 폴백)
    ENCODED_PATH=$(python3 -c "import urllib.parse, sys; print(urllib.parse.quote(sys.argv[1], safe='/'))" "$ABS_REPORT_PATH" 2>/dev/null || echo "$ABS_REPORT_PATH")
    if grep -qi microsoft /proc/version 2>/dev/null; then
        # WSL 환경
        DISTRO=$(grep '^ID=' /etc/os-release | cut -d= -f2)
        VERSION=$(grep '^VERSION_ID=' /etc/os-release | cut -d= -f2 | tr -d '"')
        DISTRO_NAME="${DISTRO^}-${VERSION}"
        VSCODE_URI="vscode://file//wsl\$/${DISTRO_NAME}${ENCODED_PATH}"
    else
        # Mac / Linux 환경
        VSCODE_URI="vscode://file${ENCODED_PATH}"
    fi
    REPORT_LINK="\n- 보고서: <${VSCODE_URI}|보고서 열기>"
fi

# Slack 메시지 구성 (에이전트 이모지 포함)
MESSAGE="${EMOJI_PREFIX}*${TITLE}*\n- 작업ID: \`${WORK_ID}\`\n- 작업이름: ${WORK_NAME}\n- 명령어: \`${COMMAND}\`\n- 상태: ${STATUS}${REPORT_LINK}"

# JSON payload 구성 (공용 함수의 3단계 폴백 체인 사용)
JSON_PAYLOAD=$(build_json_payload "$SLACK_CHANNEL_ID" "$MESSAGE")

# Slack API 호출 + 응답 검증 (공용 함수 사용)
send_slack_message "$JSON_PAYLOAD"

exit 0
