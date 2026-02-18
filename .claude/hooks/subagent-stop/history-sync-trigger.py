#!/usr/bin/env python3
"""Subagent stop history.md sync trigger (thin wrapper)
Triggers history-sync sync in background when a workflow agent subagent stops.
Original logic: history-sync-trigger.sh
"""
import os
import sys
import json
import subprocess

def main():
    stdin_data = sys.stdin.read().strip()
    if not stdin_data:
        sys.exit(0)

    try:
        data = json.loads(stdin_data)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    agent_type = data.get('agent_type', '')
    valid_types = {'init', 'planner', 'worker', 'explorer', 'reporter', 'done'}
    if agent_type not in valid_types:
        sys.exit(0)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.normpath(os.path.join(script_dir, '..', '..', '..'))

    # Try Python version first, fall back to shell
    py_target = os.path.join(project_root, '.claude', 'scripts', 'workflow', 'history_sync.py')
    sh_target = os.path.join(project_root, '.claude', 'scripts', 'workflow', 'history-sync.sh')

    if os.path.exists(py_target):
        subprocess.Popen(
            [sys.executable, py_target, 'sync'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    elif os.path.exists(sh_target):
        subprocess.Popen(
            ['bash', sh_target, 'sync'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    sys.exit(0)

if __name__ == '__main__':
    main()
