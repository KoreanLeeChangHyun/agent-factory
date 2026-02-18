#!/usr/bin/env -S python3 -u
"""Workflow transition guard (thin wrapper)
Real logic: .claude/scripts/guards/workflow_transition_guard.py
"""
import os
import sys
import subprocess

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.normpath(os.path.join(script_dir, '..', '..', '..'))
target = os.path.join(project_root, '.claude', 'scripts', 'guards', 'workflow_transition_guard.py')

stdin_data = sys.stdin.buffer.read()
result = subprocess.run(
    [sys.executable, target],
    input=stdin_data,
    capture_output=False,
)
sys.exit(result.returncode)
