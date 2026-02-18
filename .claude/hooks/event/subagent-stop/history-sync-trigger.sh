#!/bin/bash
# SubagentStop Hook: 워크플로우 서브에이전트 종료 시 history.md 자동 동기화 트리거
#
# 동작:
#   SubagentStop 이벤트 발생 시 stdin JSON에서 agent_type을 추출하여
#   워크플로우 관련 에이전트(init/planner/worker/explorer/reporter/done) 종료 시
#   history-sync.sh sync를 백그라운드로 비동기 실행
#
# 입력 (stdin JSON):
#   agent_type
#
# 비차단 원칙: 모든 에러 경로에서 exit 0 (async Hook이므로 실패해도 워크플로우 무영향)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# stdin JSON 읽기
INPUT=$(cat)
if [ -z "$INPUT" ]; then
    exit 0
fi

# JSON 필드 추출 (jq 없이 python3 사용)
AGENT_TYPE=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('agent_type',''))" 2>/dev/null) || exit 0

# 워크플로우 에이전트 필터링 (6종만 처리)
case "$AGENT_TYPE" in
    init|planner|worker|explorer|reporter|done) ;;
    *) exit 0 ;;
esac

# history-sync.sh sync를 백그라운드로 비동기 실행
bash "$SCRIPT_DIR/../../workflow/history-sync.sh" sync &

exit 0
