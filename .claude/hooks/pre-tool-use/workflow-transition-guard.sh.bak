#!/bin/bash
# 워크플로우 전이 가드 (thin wrapper)
# 실제 로직: .claude/scripts/guards/workflow-transition-guard.sh
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cat | bash "$PROJECT_ROOT/.claude/scripts/guards/workflow-transition-guard.sh"
