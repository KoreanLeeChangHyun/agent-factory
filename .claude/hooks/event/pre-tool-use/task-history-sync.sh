#!/bin/bash
# PreToolUse(Task) Hook: Task 호출 시 history.md 자동 동기화 트리거
#
# 동작:
#   PreToolUse(Task) 이벤트 발생 시 stdin JSON에서 subagent_type을 추출하여
#   워크플로우 관련 에이전트(init/planner/worker/explorer/reporter/done) 호출 시
#   history-sync.sh sync를 백그라운드로 비동기 실행
#
# 입력 (stdin JSON):
#   tool_input.subagent_type - 서브에이전트 타입
#   tool_input.prompt - workDir 포함 프롬프트 (워크플로우 여부 판별용)
#
# 비차단 원칙: 모든 에러 경로에서 exit 0 (async Hook이므로 실패해도 워크플로우 무영향)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# stdin JSON 읽기
INPUT=$(cat)
if [ -z "$INPUT" ]; then
    exit 0
fi

# JSON에서 subagent_type과 workDir 추출 (jq 없이 python3 사용)
# workflow-agent-guard.sh와 동일한 패턴: tool_input.subagent_type + tool_input.prompt에서 workDir 추출
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

# 빈 결과면 워크플로우 외 Task 호출 -> 통과
if [ -z "$RESULT" ]; then
    exit 0
fi

AGENT_TYPE="$RESULT"

# 워크플로우 에이전트 필터링 (6종만 처리)
case "$AGENT_TYPE" in
    init|planner|worker|explorer|reporter|done) ;;
    *) exit 0 ;;
esac

# history-sync.sh sync를 백그라운드로 비동기 실행
bash "$SCRIPT_DIR/../../workflow/history-sync.sh" sync &

exit 0
