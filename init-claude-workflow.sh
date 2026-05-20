#!/bin/bash
set -euo pipefail
# ==============================================================================
# init-claude-workflow.sh — backward-compatible bootstrap entrypoint
# Prefer init-agent-factory-workflow.sh for new installs.
# ==============================================================================

NEW_SCRIPT="init-agent-factory-workflow.sh"
RAW_URL="https://raw.githubusercontent.com/KoreanLeeChangHyun/claude-workflow/main/${NEW_SCRIPT}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -f "$SCRIPT_DIR/$NEW_SCRIPT" ]; then
    exec bash "$SCRIPT_DIR/$NEW_SCRIPT" "$@"
fi

command -v curl &>/dev/null || {
    printf 'curl is required to fetch %s\n' "$RAW_URL" >&2
    exit 1
}

printf 'init-claude-workflow.sh is deprecated; forwarding to %s\n' "$NEW_SCRIPT" >&2
curl -fsSL "$RAW_URL" | bash -s -- "$@"
