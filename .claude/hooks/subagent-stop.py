#!/usr/bin/env -S python3 -u
"""SubagentStop event dispatcher.

Dispatches subagent-stop hooks based on HOOK_* flags in .claude.env.
Replaces individual wrapper scripts in .claude/hooks/subagent-stop/.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dispatcher import (
    load_env_flags,
    dispatch_async,
    is_enabled,
    scripts_dir,
)


def _history_sync_trigger(stdin_data, flags):
    """Inline history-sync-trigger logic (migrated from subagent-stop/history-sync-trigger.py).

    Triggers history_sync.py sync in background when a workflow agent subagent stops.
    """
    if not is_enabled(flags, 'HOOK_HISTORY_SYNC_TRIGGER'):
        return

    try:
        data = json.loads(stdin_data)
    except (json.JSONDecodeError, ValueError):
        return

    agent_type = data.get('agent_type', '')
    valid_types = {'init', 'planner', 'worker', 'explorer', 'reporter', 'done'}
    if agent_type not in valid_types:
        return

    import subprocess
    target = scripts_dir('workflow', 'sync', 'history_sync.py')
    if os.path.exists(target):
        subprocess.Popen(
            [sys.executable, target, 'sync'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def main():
    stdin_data = sys.stdin.buffer.read()
    flags = load_env_flags()

    # usage-tracker (async)
    dispatch_async(
        'HOOK_USAGE_TRACKER',
        scripts_dir('workflow', 'sync', 'usage_sync.py'),
        stdin_data,
        flags=flags,
    )

    # history-sync-trigger (async, inline logic)
    _history_sync_trigger(stdin_data, flags)

    # All hooks are async/fire-and-forget, no exit code aggregation needed
    sys.exit(0)


if __name__ == '__main__':
    main()
