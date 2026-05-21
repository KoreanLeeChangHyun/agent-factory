#!/usr/bin/env python3
"""ensure_bin_path.sh - Injects .agent-factory/bin into the Claude Code Bash tool environment.

Called by the SessionStart hook and writes a PATH export statement to CLAUDE_ENV_FILE.
Claude Code applies the export statements in CLAUDE_ENV_FILE to subsequent Bash tool environments.

stdout: none (SessionStart hook stdout is injected into the system prompt, so nothing is printed)
stderr: debug logs when needed
exit code: 0 (always succeeds)
"""

from __future__ import annotations

import os
import sys


def main() -> None:
    """Write the .agent-factory/bin PATH export to CLAUDE_ENV_FILE.

    Uses the CLAUDE_PROJECT_DIR environment variable to determine the bin directory path.
    Exits quietly if CLAUDE_ENV_FILE is not set or the bin directory does not exist.
    """
    env_file = os.environ.get('CLAUDE_ENV_FILE', '')
    if not env_file:
        sys.exit(0)

    project_dir = os.environ.get('CLAUDE_PROJECT_DIR', '')
    if not project_dir:
        # If CLAUDE_PROJECT_DIR does not exist, it is inferred based on the hooks directory.
        # ensure_bin_path.sh is located in .agent-factory/engine/apps/hooks/
        # So ../../../../ = project root
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_dir = os.path.normpath(os.path.join(script_dir, '..', '..', '..', '..'))

    bin_dir = os.path.join(project_dir, '.agent-factory', 'bin')
    if not os.path.isdir(bin_dir):
        # Do nothing if there is no bin directory
        sys.exit(0)

    # Add PATH export to CLAUDE_ENV_FILE
    # Avoid adding duplicates if the path is already included
    current_path = os.environ.get('PATH', '')
    if bin_dir in current_path.split(':'):
        # Already included in PATH (based on current process environment)
        sys.exit(0)

    export_line = f'export PATH="{bin_dir}:$PATH"\n'

    try:
        # Skip if the file already exists and contains its path
        existing = ''
        if os.path.isfile(env_file):
            with open(env_file, 'r', encoding='utf-8') as f:
                existing = f.read()
        if bin_dir in existing:
            sys.exit(0)

        with open(env_file, 'a', encoding='utf-8') as f:
            f.write(export_line)
    except OSError:
        # Quietly exits when file writing fails
        pass

    sys.exit(0)


if __name__ == '__main__':
    main()
