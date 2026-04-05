#!/usr/bin/env -S python3 -u
"""Post-tool-use dispatcher.

Routes hook logic based on tool_name extracted from stdin JSON.
Uses dispatcher.py utilities for flag-based conditional execution.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dispatcher import (
    dispatch_async,
    load_env_flags,
    scripts_dir,
)

_scripts_dir: str = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts')
)
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from flow.session_identifier import WINDOW_PREFIX_P


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

def _handle_bash_flow_end(tool_input: dict) -> None:
    """Handle session cleanup when flow-claude end is detected.

    Detects 'flow-claude end' pattern in Bash command input and schedules
    a delayed session kill as a secondary safety net (2nd layer after
    finalization.py Step 5). Uses a 5-second delay (longer than
    finalization.py's 3 seconds) to ensure banner output completes first.

    HTTP API path (primary):
        Uses _WF_SESSION_ID + _WF_SERVER_PORT environment variables to call
        POST /terminal/workflow/kill via a background subprocess with 5s delay.

    TMUX fallback path (legacy):
        When _WF_SESSION_ID or _WF_SERVER_PORT is absent, falls back to the
        original TMUX_PANE-based tmux kill-window approach.

    If any required condition is unmet, cleanup is silently skipped (idempotent).

    Args:
        tool_input: The tool_input dict from the Bash hook payload.
    """
    command: str = tool_input.get('command', '') if isinstance(tool_input, dict) else ''
    # 명령어 시작 위치(줄 시작 또는 ; && || & 뒤)에서만 매칭 —
    # 주석/문자열 리터럴/heredoc 내부의 'flow-claude end' 오탐 방지
    if not re.search(r'(?:^|[;&|]\s*)flow-claude\s+end\b', command):
        return

    session_id: str | None = os.environ.get('_WF_SESSION_ID')
    server_port: str | None = os.environ.get('_WF_SERVER_PORT')

    if session_id and server_port:
        # HTTP API path: 5초 지연 후 POST /terminal/workflow/kill (백그라운드)
        port = server_port
        sid = session_id
        python_cmd = (
            f"import time,urllib.request,json; "
            f"time.sleep(5); "
            f"urllib.request.urlopen("
            f"urllib.request.Request("
            f"'http://127.0.0.1:{port}/terminal/workflow/kill', "
            f"data=json.dumps({{'session_id':'{sid}'}}).encode(), "
            f"headers={{'Content-Type':'application/json'}}, "
            f"method='POST'))"
        )
        subprocess.Popen(
            ['python3', '-c', python_cmd],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return

    # TMUX fallback: _WF_SESSION_ID 또는 _WF_SERVER_PORT 미설정 시 기존 tmux 경로 유지
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

    if not window_name.startswith(f'{WINDOW_PREFIX_P}T-'):
        return

    # TMUX_PANE(%N)을 직접 타겟으로 사용: 콜론 포함 윈도우명의 세션:윈도우 오해석 방지
    pane_target: str = shlex.quote(tmux_pane)
    bash_cmd: str = f'sleep 5 && tmux kill-window -t {pane_target}'

    subprocess.Popen(
        ['bash', '-c', bash_cmd],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
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
