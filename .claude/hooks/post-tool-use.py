#!/usr/bin/env -S python3 -u
"""Post-tool-use dispatcher.

Routes hook logic based on tool_name extracted from stdin JSON.
Uses dispatcher.py utilities for flag-based conditional execution.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dispatcher import (
    dispatch_async,
    load_env_flags,
    scripts_dir,
)


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

def _handle_bash_flow_end(tool_input: dict) -> None:
    """Handle tmux window cleanup when flow-claude end is detected.

    Detects 'flow-claude end' pattern in Bash command input and schedules
    a delayed tmux kill-window as a secondary safety net (2nd layer after
    finalization.py Step 5). Uses a 5-second delay (longer than
    finalization.py's 3 seconds) to ensure banner output completes first.

    Conditions required to trigger cleanup:
        1. TMUX_PANE environment variable is set.
        2. Current tmux window name starts with 'T-'.

    If any condition is unmet, cleanup is silently skipped (idempotent).

    Args:
        tool_input: The tool_input dict from the Bash hook payload.
    """
    command: str = tool_input.get('command', '') if isinstance(tool_input, dict) else ''
    if 'flow-claude end' not in command:
        return

    tmux_pane: str | None = os.environ.get('TMUX_PANE')
    if not tmux_pane:
        return

    try:
        result = subprocess.run(
            ['tmux', 'display-message', '-t', tmux_pane, '-p', '#W'],
            capture_output=True,
            text=True,
            timeout=5,
        )
        window_name: str = result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return

    if not window_name.startswith('T-'):
        return

    subprocess.Popen(
        ['nohup', 'bash', '-c', f'sleep 5 && tmux kill-window -t {window_name}'],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


# ---------------------------------------------------------------------------
# Main dispatcher
# ---------------------------------------------------------------------------

def main() -> None:
    """Dispatch post-tool-use hooks based on tool_name and file_path.

    Reads JSON from stdin, extracts tool_name and file_path, and
    dispatches async hooks as fire-and-forget. All hooks in this
    dispatcher are async; exits with 0 unconditionally.
    """
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

    # --- Bash: flow-claude end detection (tmux window cleanup, 2nd safety net) ---
    # Must be placed before the file_path guard because Bash tool has no file_path.
    if tool_name == 'Bash':
        _handle_bash_flow_end(tool_input)
        sys.exit(0)

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
