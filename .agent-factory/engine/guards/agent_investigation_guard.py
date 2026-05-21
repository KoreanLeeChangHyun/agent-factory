#!/usr/bin/env -S python3 -u
"""Main session investigation purpose Subagent blocking guard Hook script.

In the PreToolUse(Task) event, the subagent_type is Explore, general-purpose, or
If the value is unspecified and not in the allow list, the current session is not a workflow session.
Blocks the subagent call.
The session type is determined with session_identifier.get_session_type().

Allowed subagent_types: worker-opus, worker-sonnet, planner, reporter, validator

Main functions:
    main: Hook entry point, parses stdin JSON and blocks subagent for investigation purposes

Input: JSON to stdin (tool_name, tool_input)
Output: hookSpecificOutput JSON when blocking, empty output when passing.

Toggle: Environment variable HOOK_AGENT_INVESTIGATION_GUARD (false/0 = disabled, default enabled)
"""

from __future__ import annotations

import json
import os
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
from flow.session_identifier import get_session_type
from messages import (
    AGENT_INVESTIGATION_MAIN_SESSION_DENIED,
)

# List of allowed subagent_types (workflow-only subagents)
_ALLOWED_SUBAGENT_TYPES: frozenset[str] = frozenset({
    "worker-opus",
    "worker-sonnet",
    "planner",
    "reporter",
    "validator",
})


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


def _extract_subagent_type(tool_input: dict) -> str:
    """Extract subagent_type from tool_input.

    First check the top key 'subagent_type' of the tool_input dictionary,
    If not present, parsing is attempted from the 'prompt' string.

    Args:
        tool_input: tool_input dictionary of Task tools

    Returns:
        Extracted subagent_type string. Empty string if not found.
    """
    # Check top level key first
    subagent_type = tool_input.get("subagent_type", "")
    if subagent_type:
        return str(subagent_type).strip()

    # Fallback parsing from prompt string
    prompt = tool_input.get("prompt", "")
    if not isinstance(prompt, str):
        return ""

    # Subagent_type="..." or subagent_type='...' pattern search
    import re
    pattern = r'subagent_type\s*=\s*["\']([^"\']+)["\']'
    match = re.search(pattern, prompt)
    if match:
        return match.group(1).strip()

    return ""


def main() -> None:
    """Entry point of main session investigation purpose subagent blocking hook.

    When reading JSON from stdin and using the Task tool, subagent_type is used for investigation purposes.
    (Explore, general-purpose) or an unspecified value not in the allow list,
    Check if the current session is a workflow session,
    If it is not a workflow session, a deny response is output to block the subagent call.
    The session type is determined with session_identifier.get_session_type().
    """
    # Load settings from .agent-factory/.settings
    hook_flag = os.environ.get("HOOK_AGENT_INVESTIGATION_GUARD") or read_env("HOOK_AGENT_INVESTIGATION_GUARD")

    # Hook disable check (false = disabled)
    if hook_flag in ("false", "0"):
        sys.exit(0)

    # Reading JSON from stdin
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    tool_name = data.get("tool_name", "")

    # Pass if it is not a Task tool
    if tool_name != "Task":
        sys.exit(0)

    tool_input = data.get("tool_input", {})
    if not isinstance(tool_input, dict):
        sys.exit(0)

    # extract subagent_type
    subagent_type = _extract_subagent_type(tool_input)

    # subagent_type included in the allow list passes regardless of session.
    if subagent_type in _ALLOWED_SUBAGENT_TYPES:
        sys.exit(0)

    # Subagent_types (Explore, general-purpose, empty value, etc.) other than those in the allow list are candidates for blocking.
    # Session type determination: Pass if workflow, block otherwise (main, unknown)
    session_type = get_session_type()
    if session_type == "workflow":
        sys.exit(0)

    # Block if not a workflow session
    _deny(AGENT_INVESTIGATION_MAIN_SESSION_DENIED.format(subagent_type=repr(subagent_type)))


if __name__ == "__main__":
    main()
