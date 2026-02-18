#!/bin/bash
# 서브에이전트 종료 시 history.md 동기화 트리거 (thin wrapper)
# 실제 로직: 워크플로우 에이전트 종료 시 history-sync.sh sync 백그라운드 실행
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

INPUT=$(cat)
if [ -z "$INPUT" ]; then
    exit 0
fi

AGENT_TYPE=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('agent_type',''))" 2>/dev/null) || exit 0

case "$AGENT_TYPE" in
    init|planner|worker|explorer|reporter|done) ;;
    *) exit 0 ;;
esac

bash "$PROJECT_ROOT/.claude/scripts/workflow/history-sync.sh" sync &
exit 0
