#!/usr/bin/env -S python3 -u
"""Session-start dispatcher.

Dispatches SessionStart hook scripts.
Uses dispatcher.py utilities for flag-based conditional execution.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dispatcher import (
    collect_exit_codes,
    dispatch,
    load_env_flags,
    scripts_dir,
)


def main() -> None:
    """Dispatch session-start hooks.

    Reads stdin (SessionStart JSON payload) and dispatches
    the system-prompt injection script. Stdout from the dispatched
    script passes through for hook system capture.
    """
    stdin_data = sys.stdin.buffer.read()
    flags = load_env_flags()
    sync_results = []

    # --- system-prompt injection (sync, stdout passthrough) ---
    r = dispatch(
        'HOOK_SESSION_SYSTEM_PROMPT',
        scripts_dir('flow', 'inject_prompt.py'),
        stdin_data,
        flags=flags,
    )
    sync_results.append(r)

    sys.exit(collect_exit_codes(sync_results))


if __name__ == '__main__':
    main()
