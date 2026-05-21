#!/usr/bin/env -S python3 -u
"""Hook script to block dangerous commands.

Blocks dangerous commands after pattern matching in PreToolUse(Bash) event.

Main functions:
    main: Hook entry point, blocks dangerous commands after parsing stdin JSON

Input: JSON to stdin (tool_name, tool_input)
Output: hookSpecificOutput JSON when blocking, empty output when passing.
"""

from __future__ import annotations

import json
import os
import re
import sys

# Set utils package import path
_engine_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _engine_dir not in sys.path:
    sys.path.insert(0, _engine_dir)

from common import read_env

# Loading dangerous command patterns (Security priority: full blocking fallback in case of import failure)
try:
    from constants import DANGER_WHITELIST, DANGER_PATTERNS
    WHITELIST_PATTERNS: list[tuple[str, None]] = [(item["pattern"], None) for item in DANGER_WHITELIST]
    DANGER_PATTERN_LIST: list[tuple[str, str, str]] = [
        (item["pattern"], item["blocked"], item["alternative"])
        for item in DANGER_PATTERNS
    ]
except ImportError:
    print(
        "[dangerous_command_guard] CRITICAL: data.constants import failed - apply security fallback",
        file=sys.stderr,
    )
    WHITELIST_PATTERNS = []
    DANGER_PATTERN_LIST = [
        (
            r".",
            "Risk pattern data load failure (security fallback)",
            "Ask your system administrator to check the status of the data/constants.py file.",
        )
    ]


def _deny(blocked: str, alternative: str) -> None:
    """Prints the blocking JSON to stdout and terminates the process.

    Args:
        blocked: Description of blocked command or pattern
        alternative: Safe alternative instruction string
    """
    reason = f"Dangerous command detected: {blocked}. Safe alternative: {alternative}"
    result = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0)


def main() -> None:
    """Entry point of a dangerous command blocking hook.

    Read JSON from stdin to check for risk patterns when running Bash tools,
    When matching, a deny response is output to block execution.
    If it matches a whitelist pattern, the check is skipped.
    """
    # Load settings from .agent-factory/.settings
    hook_flag = os.environ.get("HOOK_DANGEROUS_COMMAND") or read_env("HOOK_DANGEROUS_COMMAND")

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

    # Whitelist check (safe patterns pass)
    for wl_pattern, _ in WHITELIST_PATTERNS:
        if re.search(wl_pattern, command):
            sys.exit(0)

    # Risk pattern inspection
    for pattern, blocked, alternative in DANGER_PATTERN_LIST:
        if re.search(pattern, command):
            _deny(blocked, alternative)

    # Passes when risk pattern does not match
    sys.exit(0)


if __name__ == "__main__":
    main()
