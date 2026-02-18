#!/bin/bash
# 위험 명령어 차단 가드 (thin wrapper)
# 실제 로직: .claude/scripts/guards/dangerous-command-guard.sh
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cat | bash "$PROJECT_ROOT/.claude/scripts/guards/dangerous-command-guard.sh"
