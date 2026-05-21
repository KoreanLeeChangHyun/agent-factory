#!/usr/bin/env -S python3 -u
"""Main branch commit blocking guard Hook script.

When the git commit command is detected in the PreToolUse (Bash) event, the current branch is
If it is main or master, it blocks.

Main functions:
    main: Hook entry point, blocks main/master branch commit after parsing stdin JSON

Input: JSON to stdin (tool_name, tool_input)
Output: hookSpecificOutput JSON when blocking, empty output when passing.

Toggle: Environment variable HOOK_MAIN_BRANCH_GUARD (false/0 = disabled, default enabled)
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys

# Set utils package import path
_engine_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _engine_dir not in sys.path:
    sys.path.insert(0, _engine_dir)

# Guard message module import path setting
_guards_dir = os.path.dirname(os.path.abspath(__file__))
if _guards_dir not in sys.path:
    sys.path.insert(0, _guards_dir)

from common import read_env
from messages import MAIN_BRANCH_COMMIT_DENIED

# git commit patterns to block on main/master branches
_GIT_COMMIT_PATTERN = re.compile(r"\bgit\s+commit\b")

# Set of protected branches
_PROTECTED_BRANCHES: frozenset[str] = frozenset({"main", "master"})


def _deny(reason: str) -> None:
    """Prints the blocking JSON to stdout and terminates the process.

    Args:
        reason: Blocking reason string
    """
    result = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0)


def _get_current_branch() -> str | None:
    """Returns the current git branch name.

    Returns:
        Current branch name string. None if git execution fails.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return None


def main() -> None:
    """Entry point for main/master branch commit blocking Hook.

    Detect the Bash tool's git commit command by reading JSON from stdin,
    If the current branch is main or master, a deny response is output and blocked.
    If git execution fails, it is treated as a safe pass (exit 0).
    """
    # Load settings from .agent-factory/.settings
    hook_flag = os.environ.get("HOOK_MAIN_BRANCH_GUARD") or read_env("HOOK_MAIN_BRANCH_GUARD")

    # Hook disable check (false = disabled)
    if hook_flag in ("false", "0"):
        sys.exit(0)

    # Reading JSON from stdin
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    tool_name = data.get("tool_name", "")

    # Pass if not Bash
    if tool_name != "Bash":
        sys.exit(0)

    tool_input = data.get("tool_input", {})
    command = tool_input.get("command", "")
    if not command:
        sys.exit(0)

    # git commit pattern matching
    if not _GIT_COMMIT_PATTERN.search(command):
        sys.exit(0)

    # Current branch query
    branch = _get_current_branch()
    if branch is None:
        # Safe pass when git execution fails
        sys.exit(0)

    # Block if main/master branch
    if branch in _PROTECTED_BRANCHES:
        _deny(MAIN_BRANCH_COMMIT_DENIED.format(branch=branch))

    # Pass if not a protected branch
    sys.exit(0)


if __name__ == "__main__":
    main()
