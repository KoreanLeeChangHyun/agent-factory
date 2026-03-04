#!/usr/bin/env -S python3 -u
"""Post-tool-use dispatcher.

Routes hook logic based on tool_name extracted from stdin JSON.
Uses dispatcher.py utilities for flag-based conditional execution.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dispatcher import (
    dispatch_async,
    load_env_flags,
    scripts_dir,
)


# ---------------------------------------------------------------------------
# Main dispatcher
# ---------------------------------------------------------------------------

def main():
    stdin_data = sys.stdin.buffer.read()

    # Parse tool_name and tool_input from JSON input
    try:
        payload = json.loads(stdin_data)
        if not isinstance(payload, dict):
            sys.exit(0)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    tool_name = payload.get('tool_name', '')
    tool_input = payload.get('tool_input', {})
    file_path = tool_input.get('file_path', '') if isinstance(tool_input, dict) else ''

    if not file_path:
        sys.exit(0)

    flags = load_env_flags()

    # --- Write|Edit: catalog-sync (async, fire-and-forget) ---
    # Trigger when a SKILL.md file under .claude/skills/ is written or edited
    if tool_name in ('Write', 'Edit'):
        if '.claude/skills/' in file_path and file_path.endswith('/SKILL.md'):
            dispatch_async(
                'HOOK_CATALOG_SYNC',
                scripts_dir('sync', 'catalog_sync.py'),
                stdin_data,
                flags=flags,
            )

    # All hooks are async/fire-and-forget, no exit code aggregation needed
    sys.exit(0)


if __name__ == '__main__':
    main()
