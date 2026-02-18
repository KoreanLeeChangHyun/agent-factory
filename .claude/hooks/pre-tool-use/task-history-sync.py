#!/usr/bin/env -S python3 -u
"""Task history sync trigger (thin wrapper)
Triggers history_sync.py sync in background when a workflow agent Task is called.
"""
import os
import sys
import json
import re
import subprocess

def main():
    stdin_data = sys.stdin.read().strip()
    if not stdin_data:
        sys.exit(0)

    try:
        data = json.loads(stdin_data)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    tool_input = data.get('tool_input', {})
    subagent_type = tool_input.get('subagent_type', '')
    if not subagent_type:
        sys.exit(0)

    prompt = tool_input.get('prompt', '')
    match = re.search(r'workDir:\s*(\S+)', prompt)
    if not match:
        sys.exit(0)

    valid_types = {'init', 'planner', 'worker', 'explorer', 'reporter', 'done'}
    if subagent_type not in valid_types:
        sys.exit(0)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.normpath(os.path.join(script_dir, '..', '..', '..'))

    py_target = os.path.join(project_root, '.claude', 'scripts', 'workflow', 'history_sync.py')

    if os.path.exists(py_target):
        subprocess.Popen(
            [sys.executable, py_target, 'sync'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    sys.exit(0)

if __name__ == '__main__':
    main()
