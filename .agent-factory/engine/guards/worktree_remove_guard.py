#!/usr/bin/env -S python3 -u
"""Hook script to guard against uncommitted changes before deleting the work tree.

Detects the ``git worktree remove`` command in the PreToolUse(Bash) event,
If there are uncommitted changes in the target worktree, they are blocked.

Pass if path extraction fails or the target directory does not exist (avoiding false positives).
Passes if there are no uncommitted changes.

Main functions:
    main: Hook entry point, blocks uncommitted work tree changes after parsing stdin JSON

Input: JSON to stdin (tool_name, tool_input)
Output: hookSpecificOutput JSON when blocking, empty output when passing.

Toggle: Environment variable HOOK_WORKTREE_REMOVE_GUARD (false/0 = disabled, default enabled)
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

from common import read_env
from flow.worktree_manager import has_uncommitted_changes

# ``git worktree remove [--force] <path>`` command pattern
_WORKTREE_REMOVE_PATTERN: str = r"\bgit\s+worktree\s+remove\b"


def _deny(worktree_path: str, status_output: str) -> None:
    """Prints the blocking JSON to stdout and terminates the process.

    Args:
        worktree_path: Worktree path where uncommitted changes were detected.
        status_output: ``git status --porcelain`` output (list of uncommitted files).
    """
    reason = (
        f"[Block worktree deletion] This is a worktree with uncommitted changes: {worktree_path} \n"
        f"List of uncommitted files: \n {status_output} \n"
        "Complete with the normal path using flow-merge."
    )
    result = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0)


def _extract_worktree_path(command: str) -> str | None:
    """Extracts the path argument from the ``git worktree remove [--force] <path>`` command.

    Skips the ``--force`` flag and returns the first non-optional argument as the path.
    If extraction fails or there are no arguments, None is returned.

    Args:
        command: Command string of Bash tool.

    Returns:
        Worktree path string. None if extraction fails.
    """
    # After ``git worktree remove``, only the arguments are parsed.
    match = re.search(_WORKTREE_REMOVE_PATTERN, command)
    if not match:
        return None

    # Extract remaining string after matching end position
    remainder = command[match.end():].strip()
    if not remainder:
        return None

    # Token separation (simple space-based separation; quoted paths are out of scope for processing)
    tokens = remainder.split()
    for token in tokens:
        # ``--force`` or ``-f`` flags are skipped
        if token in ("--force", "-f"):
            continue
        # Returns the first non-optional argument as a path
        return token

    return None


def _get_status_output(worktree_path: str) -> str:
    """Returns the output of ``git status --porcelain`` in the worktree path.

    If the command execution fails, an empty string is returned.

    Args:
        worktree_path: Worktree directory path to check.

    Returns:
        ``git status --porcelain`` standard output. Empty string on failure.
    """
    try:
        result = subprocess.run(
            ["git", "-C", worktree_path, "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return ""


def main() -> None:
    """Entry point of the uncommitted change defense guard hook before deleting the work tree.

    Detect the Bash tool's ``git worktree remove`` command by reading JSON from stdin,
    If there are uncommitted changes in the target worktree, a deny response is output to block deletion.

    If path extraction fails, directory does not exist, or there is no commit, it passes.
    """
    # Load settings from .agent-factory/.settings
    hook_flag = os.environ.get("HOOK_WORKTREE_REMOVE_GUARD") or read_env("HOOK_WORKTREE_REMOVE_GUARD")

    # Hook disable check (false/0 = disabled)
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

    # Passes if ``git worktree remove`` pattern is not present
    if not re.search(_WORKTREE_REMOVE_PATTERN, command):
        sys.exit(0)

    # Extract worktree path from command (pass on failure — avoid false positives)
    worktree_path = _extract_worktree_path(command)
    if not worktree_path:
        sys.exit(0)

    # Pass if not a directory (already deleted path, etc.)
    if not os.path.isdir(worktree_path):
        sys.exit(0)

    # Check for uncommitted changes (if failed, return False → pass)
    if not has_uncommitted_changes(worktree_path):
        sys.exit(0)

    # There are uncommitted changes → Blocked
    status_output = _get_status_output(worktree_path)
    _deny(worktree_path, status_output)


if __name__ == "__main__":
    main()
