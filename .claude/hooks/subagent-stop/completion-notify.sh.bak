#!/bin/bash
# Worker/Reporter 완료 데스크톱 알림 (thin wrapper)
# 실제 로직: .claude/scripts/workflow/completion-notify.sh
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cat | bash "$PROJECT_ROOT/.claude/scripts/workflow/completion-notify.sh"
