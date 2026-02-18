#!/bin/bash
# SubagentStop Hook: Worker/Reporter 완료 시 데스크톱 알림 발송
#
# 동작:
#   SubagentStop 이벤트 발생 시 stdin JSON에서 agent_type, agent_id를 추출하여
#   worker 또는 reporter 완료 시점에 데스크톱 알림을 발송
#
# 입력 (stdin JSON):
#   agent_type, agent_id
#
# 비차단 원칙: 모든 에러 경로에서 exit 0 (알림 실패가 워크플로우에 영향 주지 않음)

set -euo pipefail

# stdin JSON 읽기
INPUT=$(cat)
if [ -z "$INPUT" ]; then
    exit 0
fi

# JSON 필드 추출 (jq 없이 python3 사용)
AGENT_TYPE=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('agent_type',''))" 2>/dev/null) || exit 0
AGENT_ID=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('agent_id',''))" 2>/dev/null) || exit 0

# worker 또는 reporter만 알림 발송 (init, planner는 무시)
case "$AGENT_TYPE" in
    worker|reporter) ;;
    *) exit 0 ;;
esac

# 알림 제목/본문 구성
TITLE="Claude Code: ${AGENT_TYPE^} 완료"
BODY="${AGENT_ID} 태스크 완료"

# OS 감지 및 알림 발송
case "$(uname -s)" in
    Linux)
        if command -v notify-send >/dev/null 2>&1; then
            notify-send "$TITLE" "$BODY" 2>/dev/null || true
        fi
        ;;
    Darwin)
        osascript -e "display notification \"$BODY\" with title \"$TITLE\"" 2>/dev/null || true
        ;;
esac

exit 0
