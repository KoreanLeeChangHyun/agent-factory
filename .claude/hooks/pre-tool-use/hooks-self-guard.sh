#!/bin/bash
# hooks 디렉토리 자기 보호 가드 (thin wrapper)
# 실제 로직: .claude/scripts/guards/hooks-self-guard.sh
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cat | bash "$PROJECT_ROOT/.claude/scripts/guards/hooks-self-guard.sh"
