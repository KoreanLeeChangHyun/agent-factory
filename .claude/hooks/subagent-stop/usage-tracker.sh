#!/bin/bash
# 서브에이전트 토큰 사용량 추적 (thin wrapper)
# 실제 로직: .claude/scripts/workflow/usage-tracker.sh
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cat | bash "$PROJECT_ROOT/.claude/scripts/workflow/usage-tracker.sh"
