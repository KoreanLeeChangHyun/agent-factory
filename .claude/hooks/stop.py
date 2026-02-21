#!/usr/bin/env -S python3 -u
"""Stop event dispatcher.

Dispatches stop hooks based on HOOK_* flags in .claude.env.
Replaces individual wrapper scripts in .claude/hooks/stop/.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dispatcher import load_env_flags, dispatch, scripts_dir, collect_exit_codes


def main():
    stdin_data = sys.stdin.buffer.read()
    flags = load_env_flags()

    results = []

    # workflow-auto-continue (sync)
    results.append(dispatch(
        'HOOK_WORKFLOW_AUTO_CONTINUE',
        scripts_dir('workflow', 'hooks', 'workflow_auto_continue.py'),
        stdin_data,
        flags=flags,
    ))

    sys.exit(collect_exit_codes(results))


if __name__ == '__main__':
    main()
