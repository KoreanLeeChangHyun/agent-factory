#!/bin/bash
# Task 호출 시 history.md 자동 동기화 트리거 (thin wrapper)
# 실제 로직: 워크플로우 에이전트 Task 호출 시 history-sync.sh sync 백그라운드 실행
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

INPUT=$(cat)
if [ -z "$INPUT" ]; then
    exit 0
fi

RESULT=$(echo "$INPUT" | python3 -c "
import sys, json, re

data = json.load(sys.stdin)
tool_input = data.get('tool_input', {})

subagent_type = tool_input.get('subagent_type', '')
if not subagent_type:
    print('')
    sys.exit(0)

prompt = tool_input.get('prompt', '')
match = re.search(r'workDir:\s*(\S+)', prompt)
if not match:
    print('')
    sys.exit(0)

print(subagent_type)
" 2>/dev/null) || exit 0

if [ -z "$RESULT" ]; then
    exit 0
fi

case "$RESULT" in
    init|planner|worker|explorer|reporter|done) ;;
    *) exit 0 ;;
esac

bash "$PROJECT_ROOT/.claude/scripts/workflow/history-sync.sh" sync &
exit 0
