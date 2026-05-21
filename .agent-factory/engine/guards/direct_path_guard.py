#!/usr/bin/env -S python3 -u
"""Direct route call blocking guard Hook script.

In the PreToolUse(Bash) event, make a direct path call of the python3 .agent-factory/engine/ pattern.
A guard script that detects and guides the use of flow-* alias.

Main functions:
    main: Hook entry point, blocks direct route calls after parsing stdin JSON

Input: JSON to stdin (tool_name, tool_input)
Output: hookSpecificOutput JSON when blocking, empty output when passing.

Toggle: Environment variable HOOK_DIRECT_PATH_GUARD (false/0 = disabled, default enabled)
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
from messages import DIRECT_PATH_CALL_DENIED

# Direct path call detection pattern (detection of both relative and absolute paths)
_DIRECT_PATH_PATTERN = re.compile(
    r"python3(?:\s+-u)?\s+(?:\$CLAUDE_PROJECT_DIR/)?"
    r"(?:\.agent-factory/engine/|/[^\s]*\.agent-factory/engine/)"
)

# Allowed exception patterns (fixed calling routes in settings.json hooks/statusLine, etc.)
_ALLOWED_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"python3(?:\s+-u)?\s+(?:\$CLAUDE_PROJECT_DIR/)?(?:\.agent-factory/|/[^\s]*\.agent-factory/)hooks/"),
    re.compile(r"python3(?:\s+-u)?\s+(?:\$CLAUDE_PROJECT_DIR/)?(?:\.agent-factory/|/[^\s]*\.agent-factory/)engine/(?:apps/hooks/)?statusline\.py"),
    re.compile(r"python3(?:\s+-u)?\s+(?:\$CLAUDE_PROJECT_DIR/)?(?:\.agent-factory/|/[^\s]*\.agent-factory/)board/server\.py"),
    re.compile(r"python3(?:\s+-u)?\s+(?:\$CLAUDE_PROJECT_DIR/)?(?:\.agent-factory/|/[^\s]*\.agent-factory/)engine/(?:apps/cli/)?claude_edit\.py"),
]

# Pattern allowing history_sync.py calls following the hook dispatcher in && chains
# Example (relative path): python3 .agent-factory/hooks/... && python3 .agent-factory/engine/adapters/sync/history_sync.py ...
# Example (absolute path): python3 /path/.agent-factory/hooks/... && python3 /path/.agent-factory/engine/adapters/sync/history_sync.py ...
_CHAINED_HISTORY_SYNC_PATTERN = re.compile(
    r"python3(?:\s+-u)?\s+(?:\$CLAUDE_PROJECT_DIR/)?"
    r"(?:\.agent-factory/|/[^\s]*\.agent-factory/)hooks/\S*\s*&&\s*"
    r"python3(?:\s+-u)?\s+(?:\$CLAUDE_PROJECT_DIR/)?"
    r"(?:\.agent-factory/engine/(?:adapters/)?sync/|/[^\s]*\.agent-factory/engine/(?:adapters/)?sync/)history_sync\.py"
)

# Script file name -> alias mapping
ALIAS_MAP: dict[str, str] = {
    "update_state.py": "flow-update",
    "skill_mapper.py": "flow-skillmap",
    "state.py": "flow-skill",
    "skill_state_manager.py": "flow-skill",
    "plan_validator.py": "flow-validate",
    "prompt_validator.py": "flow-validate-p",
    "garbage_collect.py": "flow-gc",
    "kanban.py": "flow-kanban",
    "merge_pipeline.py": "flow-merge",
    "history_sync.py": "flow-history",
    "catalog_sync.py": "flow-catalog",
    "git_config.py": "flow-gitconfig",
    "project_detector.py": "flow-detect",
    "project_skill_detector.py": "flow-detect",
    "migrate_runs_fold.py": "flow-migrate-runs",
}

# Pattern to extract only the file name from the script file name (both relative and absolute paths supported)
_SCRIPT_NAME_PATTERN = re.compile(
    r"python3(?:\s+-u)?\s+(?:\$CLAUDE_PROJECT_DIR/)?"
    r"(?:\.agent-factory/engine/|/[^\s]*\.agent-factory/engine/)(?:\S+/)?(\S+\.py)"
)


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


def _extract_script_name(command: str) -> str | None:
    """Extract the .agent-factory/engine/ subscript file name from the command.

    Args:
        command: Bash command string

    Returns:
        Script file name (e.g. "kanban.py") or None
    """
    match = _SCRIPT_NAME_PATTERN.search(command)
    if match:
        return match.group(1)
    return None


def _is_allowed(command: str) -> bool:
    """Check whether the command corresponds to the allowed exception pattern.

    Args:
        command: Bash command string

    Returns:
        True if an exception is allowed, False if it is a blocked exception.
    """
    # Allowed exception pattern check
    for pattern in _ALLOWED_PATTERNS:
        if pattern.search(command):
            return True

    # Allow history_sync.py call after hook dispatcher in && chain
    if _CHAINED_HISTORY_SYNC_PATTERN.search(command):
        return True

    return False


def main() -> None:
    """Entry point for direct route call blocking guard Hook.

    Detect direct calls to python3 .agent-factory/engine/ from Bash tools by reading JSON from stdin,
    Blocks by outputting a deny response that guides the use of flow-* alias.
    Exceptions are allowed for fixed calling routes in settings.json.
    """
    # Load settings from .agent-factory/.settings
    hook_flag = os.environ.get("HOOK_DIRECT_PATH_GUARD") or read_env("HOOK_DIRECT_PATH_GUARD")

    # Hook disable check (not set or false = disabled)
    if not hook_flag or hook_flag in ("false", "0"):
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

    # Pass if there is no direct route call pattern
    if not _DIRECT_PATH_PATTERN.search(command):
        sys.exit(0)

    # Allow exception check
    if _is_allowed(command):
        sys.exit(0)

    # Script file name extraction and alias mapping
    script_name = _extract_script_name(command)
    if script_name and script_name in ALIAS_MAP:
        alias_name = ALIAS_MAP[script_name]
        _deny(DIRECT_PATH_CALL_DENIED.format(
            script_name=script_name,
            alias_name=alias_name,
        ))
    elif script_name:
        # Scripts not in ALIAS_MAP (hook only, etc.) - General blocking message
        _deny(DIRECT_PATH_CALL_DENIED.format(
            script_name=script_name,
            alias_name="(No applicable alias - may be a hook/internal-only script)",
        ))
    else:
        # General blocking when script name extraction fails
        _deny(DIRECT_PATH_CALL_DENIED.format(
            script_name=".agent-factory/engine/...",
            alias_name="flow-*",
        ))


if __name__ == "__main__":
    main()
