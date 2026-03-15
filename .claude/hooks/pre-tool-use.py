#!/usr/bin/env -S python3 -u
"""Pre-tool-use dispatcher.

Routes hook logic based on tool_name extracted from stdin JSON.
Uses dispatcher.py utilities for flag-based conditional execution.

라우팅 테이블:
  Write|Edit|Bash  -> hooks_self_guard        (HOOK_HOOKS_SELF_PROTECT, sync)
  AskUserQuestion  -> slack_ask               (HOOK_SLACK_ASK, async)
  Bash             -> dangerous_command_guard  (HOOK_DANGEROUS_COMMAND, sync)
  Bash             -> main_branch_guard        (HOOK_MAIN_BRANCH_GUARD, sync)
  Bash             -> kanban_subcommand_guard  (HOOK_KANBAN_SUBCOMMAND_GUARD, sync)
  Write|Edit|Bash  -> main_session_guard       (HOOK_MAIN_SESSION_GUARD, sync)
  Task             -> agent_investigation_guard (HOOK_AGENT_INVESTIGATION_GUARD, sync)
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dispatcher import (
    collect_exit_codes,
    dispatch,
    dispatch_async,
    load_env_flags,
    scripts_dir,
)


# ---------------------------------------------------------------------------
# Main dispatcher
# ---------------------------------------------------------------------------

def main() -> None:
    """Dispatch pre-tool-use hooks based on tool_name.

    Reads JSON from stdin, extracts tool_name, and dispatches
    the appropriate sync or async hook scripts. Exits with the
    first non-zero exit code from synchronous hooks.
    """
    stdin_data = sys.stdin.buffer.read()

    # Parse tool_name from JSON input
    try:
        payload = json.loads(stdin_data)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    tool_name = payload.get('tool_name', '')

    flags = load_env_flags()
    sync_results = []
    # Other tool_name values (Read, Glob, Grep, WebFetch, etc.) pass through without hook processing

    # --- Write|Edit|Bash: hooks-self-guard (sync) ---
    if tool_name in ('Write', 'Edit', 'Bash'):
        r = dispatch(
            'HOOK_HOOKS_SELF_PROTECT',
            scripts_dir('guards', 'hooks_self_guard.py'),
            stdin_data,
            flags=flags,
        )
        sync_results.append(r)

    # --- AskUserQuestion: slack-ask (async, fire-and-forget) ---
    if tool_name == 'AskUserQuestion':
        dispatch_async(
            'HOOK_SLACK_ASK',
            scripts_dir('slack', 'slack_ask.py'),
            stdin_data,
            flags=flags,
        )

    # --- Bash: dangerous-command-guard (sync) ---
    if tool_name == 'Bash':
        r = dispatch(
            'HOOK_DANGEROUS_COMMAND',
            scripts_dir('guards', 'dangerous_command_guard.py'),
            stdin_data,
            flags=flags,
        )
        sync_results.append(r)

    # --- Bash: main-branch-guard (sync) ---
    if tool_name == 'Bash':
        r = dispatch(
            'HOOK_MAIN_BRANCH_GUARD',
            scripts_dir('guards', 'main_branch_guard.py'),
            stdin_data,
            flags=flags,
        )
        sync_results.append(r)

    # --- Bash: kanban-subcommand-guard (sync) ---
    if tool_name == 'Bash':
        r = dispatch(
            'HOOK_KANBAN_SUBCOMMAND_GUARD',
            scripts_dir('guards', 'kanban_subcommand_guard.py'),
            stdin_data,
            flags=flags,
        )
        sync_results.append(r)

    # --- Write|Edit|Bash: main-session-guard (sync) ---
    if tool_name in ('Write', 'Edit', 'Bash'):
        r = dispatch(
            'HOOK_MAIN_SESSION_GUARD',
            scripts_dir('guards', 'main_session_guard.py'),
            stdin_data,
            flags=flags,
        )
        sync_results.append(r)

    # --- Task: agent-investigation-guard (sync) ---
    if tool_name == 'Task':
        r = dispatch(
            'HOOK_AGENT_INVESTIGATION_GUARD',
            scripts_dir('guards', 'agent_investigation_guard.py'),
            stdin_data,
            flags=flags,
        )
        sync_results.append(r)

    # Aggregate sync exit codes; first non-zero blocks the tool
    sys.exit(collect_exit_codes(sync_results))


if __name__ == '__main__':
    main()
