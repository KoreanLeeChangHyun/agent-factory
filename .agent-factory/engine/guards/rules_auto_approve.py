#!/usr/bin/env -S python3 -u
r"""`.claude/rules/` path automatic approval guard Hook script.

In the PreToolUse(Write|Edit) event, detect a request targeting a `.claude/rules/` subfile and
Returns `permissionDecision: allow` immediately.

background:
    Claude Code classifies the `.claude/` directory as a sensitive file and prevents it from being written/edited.
    Prompt for user approval. `.claude/rules/` is the workflow rules file, so
    Worker agents must be able to freely modify it.

Main functions:
    main: Hook entry point, returns allow when conditions are met after parsing stdin JSON

Input: JSON to stdin (tool_name, tool_input)
Output: permissionDecision: allow JSON if condition is met, empty output if not met

Security constraints:
    - Only `.claude/rules/` children are accepted (regular expression: r'\.claude/rules/')
    - Other sensitive paths such as `.claude/settings.json` and `.claude/settings.local.json` are not approved.
    - Other `.claude/` paths, such as `.claude/skills/`, `.claude/commands/`, and `.claude/agents/`, are also not accepted.

Toggle:
    When setting the environment variable HOOK_RULES_AUTO_APPROVE=false, this guard is disabled.
    When disabled, the default approval prompt behavior of existing Claude Code is maintained.
"""

from __future__ import annotations

import json
import os
import sys

# Set utils package import path
_engine_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _engine_dir not in sys.path:
    sys.path.insert(0, _engine_dir)

from common import read_env

# Path keyword that only allows children of `.claude/rules/`
_RULES_PATH_KEYWORD = ".claude/rules/"


def _allow(reason: str) -> None:
    """Prints the auto-acknowledgment JSON to stdout and terminates the process.

    Args:
        reason: approval reason string
    """
    result = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "permissionDecisionReason": reason,
        }
    }
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0)


def main() -> None:
    """Entry point for the `rules/` path auto-approval guard hook.

    Read the JSON from stdin so that the Write/Edit tool can create a `.claude/rules/` subfile.
    Allow is returned immediately when targeted.
    Disabled when HOOK_RULES_AUTO_APPROVE=false is set.
    """
    # Load settings from .agent-factory/.settings
    hook_flag = os.environ.get("HOOK_RULES_AUTO_APPROVE") or read_env("HOOK_RULES_AUTO_APPROVE")

    # Hook disable check (false = disabled)
    if hook_flag in ("false", "0"):
        sys.exit(0)

    # Reading JSON from stdin
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    tool_name = data.get("tool_name", "")

    # Pass if not Write or Edit
    if tool_name not in ("Write", "Edit"):
        sys.exit(0)

    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    if not file_path:
        sys.exit(0)

    # Check if it is a subpath of `.claude/rules/`
    # Security: Only allow `.claude/rules/` subdirections, no other `.claude/` paths are allowed.
    if _RULES_PATH_KEYWORD in file_path:
        _allow("auto-approve .claude/rules/ path")

    # Passes as empty output when conditions are not met (maintains existing operation)
    sys.exit(0)


if __name__ == "__main__":
    main()
