#!/usr/bin/env -S python3 -u
"""research/review session Write/Edit/Bash blocking guard Hook script.

In the PreToolUse(Write|Edit|Bash) event, the current session is the workflow session and
If the command of the active workflow is research or review, code modification is blocked.

Main functions:
    main: Hook entry point, parse stdin JSON and block research/review session Write/Edit/Bash

Input: JSON to stdin (tool_name, tool_input)
Output: hookSpecificOutput JSON when blocking, empty output when passing.

Toggle: Environment variable HOOK_READONLY_SESSION_GUARD (false/0 = disabled, default enabled)
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

from common import load_json_file, read_env, resolve_project_root, scan_active_workflows
from flow.session_identifier import get_session_type
from messages import (
    READONLY_SESSION_BASH_MODIFY_DENIED,
    READONLY_SESSION_WRITE_EDIT_DENIED,
)

# Read-only command list (code modification is prohibited in these commands)
_READONLY_COMMANDS = ("research", "review")

# Command pattern that allows Bash tools to modify files (same as main_session_guard.py)
_BASH_FILE_MODIFY_PATTERNS: list[str] = [
    r"\bsed\s+-i",                               # sed inplace
    r"\bawk\s+.*-i\s+inplace",                   # awk inplace
    r"\b(echo|printf)\s+.*\s*>{1,2}\s*\S",       # echo/printf redirect
    r"\btee\s+(-a\s+)?\S",                       # write tee
    r"\bcat\s*<<",                               # heredoc redirect
    r"\bcp\s+",                                  # copy files
    r"\bmv\s+",                                  # move files
    r"\bpython3?\s+(-c\s+|.*\bopen\b.*\bwrite\b)",  # python -c open write
    r"\bperl\s+-.*[pi]",                         # perl inplace
    r"(?:^|[;&|]\s*)\binstall\s+",               # install command (excluding subcommands)
    r"\bdd\s+",                                  # dd command
]

# .agent-factory/ subpath pattern (allows Report/History Write/Edit)
_WORKFLOW_PATH_PATTERN = re.compile(r"[/\\]?\.claude\.workflow[/\\]")

# User memory directory pattern: ~/.claude/projects/<encoded>/memory/** matching
# Same policy as main_session_guard.py (allow memory writing in research/review sessions as well)
_MEMORY_DIR_PATTERN: re.Pattern[str] = re.compile(
    r"(?:^|/)\.claude/projects/[^/]+/memory(?:/|$)"
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


def _get_workflow_command() -> str | None:
    """Returns the command field of the active workflow.

    Check the WORKFLOW_WORK_DIR environment variable first,
    If not, it scans the .workflow/ directory and reads the most recent .context.json.

    Returns:
        command string. None if search fails.
    """
    project_root = resolve_project_root()

    # 1. Check the WORKFLOW_WORK_DIR environment variable
    env_work_dir = os.environ.get("WORKFLOW_WORK_DIR", "").strip()
    if env_work_dir:
        abs_work_dir = (
            os.path.join(project_root, env_work_dir)
            if not os.path.isabs(env_work_dir)
            else env_work_dir
        )
        ctx = load_json_file(os.path.join(abs_work_dir, ".context.json"))
        if ctx and isinstance(ctx, dict):
            command = ctx.get("command", "")
            if command:
                return command

    # 2. Scan the .workflow/ directory
    try:
        registry = scan_active_workflows(project_root=project_root)
        if not registry:
            return None

        # Select the most recent workflow by updated_at
        best_entry = None
        best_updated = ""
        for _key, entry in registry.items():
            work_dir = entry.get("workDir", "")
            abs_wd = (
                os.path.join(project_root, work_dir)
                if not os.path.isabs(work_dir)
                else work_dir
            )
            status = load_json_file(os.path.join(abs_wd, "status.json"))
            updated_at = status.get("updated_at", "") if isinstance(status, dict) else ""
            if updated_at >= best_updated:
                best_updated = updated_at
                best_entry = entry

        if best_entry:
            return best_entry.get("command", "") or None
    except Exception:
        pass

    return None


def _strip_quoted_args(command: str) -> str:
    """Replaces the contents of the area surrounded by quotation marks in the command string with an empty string.

    Args:
        command: Original command string from Bash tool

    Returns:
        A string with the content inside the quotes removed.
    """
    command = re.sub(r'"(?:[^"\\]|\\.)*"', '""', command)
    command = re.sub(r"'(?:[^'\\]|\\.)*'", "''", command)
    return command


def _extract_command_positions(command: str) -> list[str]:
    """Splits the command string by the pipe/chain delimiter and returns a list of segments.

    Args:
        command: command string complete with quoted strip

    Returns:
        A list of strings with leading spaces removed from each segment.
    """
    parts = re.split(r'&&|\|\||(?<!\|)\|(?!\|)|;', command)
    return [part.lstrip() for part in parts if part.strip()]


def _is_bash_file_modify(command: str) -> bool:
    """Checks whether a file modification pattern is included in the Bash command.

    After first removing the argument area surrounded by quotation marks,
    Divide segments with pipe/chain separators
    Check the _BASH_FILE_MODIFY_PATTERNS pattern in each segment.

    Args:
        command: Command string of Bash tool

    Returns:
        True if the file modification pattern matches, False otherwise.
    """
    stripped = _strip_quoted_args(command)
    segments = _extract_command_positions(stripped)
    for segment in segments:
        for pattern in _BASH_FILE_MODIFY_PATTERNS:
            if re.search(pattern, segment):
                return True
    return False


def _is_workflow_path(file_path: str) -> bool:
    """Check whether the file path is under .workflow/.

    Args:
        file_path: File path to check

    Returns:
        True if it is a .workflow/ subpath.
    """
    return bool(_WORKFLOW_PATH_PATTERN.search(file_path))


def _is_memory_path(path: str) -> bool:
    """Check whether the file path is under the user memory directory.

    Matches ~/.claude/projects/<encoded>/memory/ or its subpath.
    Same logic as main_session_guard.py.

    Args:
        path: File path to check (absolute path or ~start path)

    Returns:
        True if it is a subpath of the memory directory, False otherwise.
    """
    if not path:
        return False
    expanded = os.path.expanduser(path)
    return bool(_MEMORY_DIR_PATTERN.search(expanded))


def main() -> None:
    """Research/review session Write/Edit/Bash Blocking Hook's entry point.

    When using Write/Edit/Bash tools by reading JSON from stdin, the current session
    If it is a workflow session and the command is research/review,
    Blocks code modification by outputting a deny response.

    In non-workflow sessions, it unconditionally passes.
    Write/Edit of .workflow/ subfiles is allowed.
    """
    # Load settings from .agent-factory/.settings
    hook_flag = os.environ.get("HOOK_READONLY_SESSION_GUARD") or read_env("HOOK_READONLY_SESSION_GUARD")

    # Hook disable check (false/0 = disabled)
    if hook_flag in ("false", "0"):
        sys.exit(0)

    # Reading JSON from stdin
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    tool_name = data.get("tool_name", "")

    # Pass if not Write, Edit, or Bash
    if tool_name not in ("Write", "Edit", "Bash"):
        sys.exit(0)

    # Determine session type -- pass if not a workflow session (not a concern of this guard)
    session_type = get_session_type()
    if session_type != "workflow":
        sys.exit(0)

    # --- Workflow session confirmed, command determination ---

    command = _get_workflow_command()

    # Passes when command inquiry fails (prevents false positives)
    if command is None:
        sys.exit(0)

    # Extract the first segment of the command (support chain command: "research>implement" -> "research")
    first_segment = command.split(">")[0].strip()

    # Passes if implement command
    if first_segment not in _READONLY_COMMANDS:
        sys.exit(0)

    # --- research/review command confirmed, blocking determined ---

    tool_input = data.get("tool_input", {})

    # Write/Edit tools: .workflow/ sub or memory directory sub is allowed
    if tool_name in ("Write", "Edit"):
        file_path = tool_input.get("file_path", "")
        if _is_workflow_path(file_path) or _is_memory_path(file_path):
            sys.exit(0)
        _deny(READONLY_SESSION_WRITE_EDIT_DENIED)

    # Bash tool: Block only file modification patterns
    if tool_name == "Bash":
        command_str = tool_input.get("command", "")
        if _is_bash_file_modify(command_str):
            _deny(READONLY_SESSION_BASH_MODIFY_DENIED)
        sys.exit(0)

    # Unknown tool: Passed
    sys.exit(0)


if __name__ == "__main__":
    main()
