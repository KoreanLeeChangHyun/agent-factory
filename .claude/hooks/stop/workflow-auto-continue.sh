#!/bin/bash
# 워크플로우 자동 계속 (thin wrapper)
# 실제 로직: .claude/scripts/workflow/workflow-auto-continue.sh
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cat | bash "$PROJECT_ROOT/.claude/scripts/workflow/workflow-auto-continue.sh"
