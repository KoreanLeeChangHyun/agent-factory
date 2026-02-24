#!/usr/bin/env -S python3 -u
"""Pre-tool-use dispatcher.

Routes hook logic based on tool_name extracted from stdin JSON.
Uses dispatcher.py utilities for flag-based conditional execution.
"""
import json
import sys

from dispatcher import (
    collect_exit_codes,
    dispatch,
    dispatch_async,
    load_env_flags,
    run_inline,
    scripts_dir,
)


# ---------------------------------------------------------------------------
# Inline logic: task-history-sync
# ---------------------------------------------------------------------------

def _task_history_sync_main(stdin_data):
    """Trigger history_sync.py in background when a workflow agent Task is called."""
    import os
    import re
    import subprocess

    if isinstance(stdin_data, bytes):
        text = stdin_data.decode('utf-8', errors='replace')
    else:
        text = stdin_data

    text = text.strip()
    if not text:
        return 0

    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return 0

    tool_input = data.get('tool_input', {})
    subagent_type = tool_input.get('subagent_type', '')
    if not subagent_type:
        return 0

    prompt = tool_input.get('prompt', '')
    match = re.search(r'workDir:\s*(\S+)', prompt)
    if not match:
        return 0

    valid_types = {'init', 'planner', 'indexer', 'worker', 'explorer', 'validator', 'reporter', 'strategy', 'done'}
    if subagent_type not in valid_types:
        return 0

    py_target = scripts_dir('workflow', 'sync', 'history_sync.py')
    if os.path.exists(py_target):
        subprocess.Popen(
            [sys.executable, py_target, 'sync'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    return 0


# ---------------------------------------------------------------------------
# Main dispatcher
# ---------------------------------------------------------------------------

def main():
    stdin_data = sys.stdin.buffer.read()

    # Parse tool_name from JSON input
    try:
        payload = json.loads(stdin_data)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    tool_name = payload.get('tool_name', '')

    flags = load_env_flags()
    sync_results = []

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

    # --- Bash: devops-dangerous-guard (sync) ---
    if tool_name == 'Bash':
        r = dispatch(
            'HOOK_DANGEROUS_COMMAND',
            scripts_dir('guards', 'dangerous_command_guard.py'),
            stdin_data,
            flags=flags,
        )
        sync_results.append(r)

    # --- Bash: workflow-transition-guard (sync) ---
    if tool_name == 'Bash':
        r = dispatch(
            'HOOK_WORKFLOW_TRANSITION',
            scripts_dir('guards', 'workflow_transition_guard.py'),
            stdin_data,
            flags=flags,
        )
        sync_results.append(r)

    # --- Task: workflow-agent-guard (sync) ---
    if tool_name == 'Task':
        r = dispatch(
            'HOOK_WORKFLOW_AGENT',
            scripts_dir('guards', 'workflow_agent_guard.py'),
            stdin_data,
            flags=flags,
        )
        sync_results.append(r)

    # --- Task: task-history-sync (async via inline) ---
    if tool_name == 'Task':
        run_inline(
            'HOOK_TASK_HISTORY_SYNC',
            _task_history_sync_main,
            stdin_data,
            flags=flags,
        )

    # Aggregate sync exit codes; first non-zero blocks the tool
    sys.exit(collect_exit_codes(sync_results))


if __name__ == '__main__':
    main()
