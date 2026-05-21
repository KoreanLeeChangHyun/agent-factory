#!/usr/bin/env -S python3 -u
"""flow-conveyor subcommand validation guard Hook script.

By parsing the subcommand of the flow-conveyor command in the PreToolUse(Bash) event,
Block the use of invalid subcommands.

Main functions:
    main: Hook entry point, blocks invalid subcommands after parsing stdin JSON

Input: JSON to stdin (tool_name, tool_input)
Output: hookSpecificOutput JSON when blocking, empty output when passing.

Toggle: Environment variable HOOK_CONVEYOR_SUBCOMMAND_GUARD (false/0 = disabled, default enabled)
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

# Guard message module import path setting
_guards_dir = os.path.dirname(os.path.abspath(__file__))
if _guards_dir not in sys.path:
    sys.path.insert(0, _guards_dir)

from common import read_env
from messages import CONVEYOR_INVALID_SUBCOMMAND, CONVEYOR_SUBMIT_REMOVED

# flow-conveyor valid subcommand set
VALID_SUBCOMMANDS: frozenset[str] = frozenset({
    "create",
    "move",
    "complete",
    "delete",
    "update-title",
    "update",
    "update-prompt",
    "update-result",
    "link",
    "unlink",
    "list",   # WorkRequest list inquiry
    "board",  # Check overall Conveyor board status
    "show",   # View specific work_request details
})

# flow-conveyor command detection and subcommand extraction pattern
# Parse the first argument after flow-conveyor as a subcommand
_FLOW_CONVEYOR_PATTERN = re.compile(r"\bflow-conveyor\s+([a-zA-Z][\w-]*)")

# The Submit transient step has been removed, so submit cannot be used as the target argument of move.
_FLOW_CONVEYOR_MOVE_SUBMIT_PATTERN = re.compile(r"\bflow-conveyor\s+move\s+WR-\d+\s+submit\b")


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


def main() -> None:
    """Entry point of flow-conveyor subcommand validation hook.

    Detect the Bash tool's flow-conveyor command by reading JSON from stdin,
    If the subcommand is not in the valid set, it outputs a deny response and blocks it.
    """
    # Load settings from .agent-factory/.settings
    hook_flag = os.environ.get("HOOK_CONVEYOR_SUBCOMMAND_GUARD") or read_env("HOOK_CONVEYOR_SUBCOMMAND_GUARD")

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

    # Pass if flow-conveyor command is not included
    if "flow-conveyor" not in command:
        sys.exit(0)

    # Subcommand extraction
    match = _FLOW_CONVEYOR_PATTERN.search(command)
    if not match:
        # Passes if there is only flow-conveyor and no subcommands (help, etc.)
        sys.exit(0)

    subcommand = match.group(1)

    # Valid subcommand check
    if subcommand in VALID_SUBCOMMANDS:
        if subcommand == "move" and _FLOW_CONVEYOR_MOVE_SUBMIT_PATTERN.search(command):
            _deny(CONVEYOR_SUBMIT_REMOVED)
        sys.exit(0)

    # Blocking invalid subcommands
    valid_list = ", ".join(sorted(VALID_SUBCOMMANDS))
    _deny(CONVEYOR_INVALID_SUBCOMMAND.format(subcommand=subcommand, valid_list=valid_list))


if __name__ == "__main__":
    main()
