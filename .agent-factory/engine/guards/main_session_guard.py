#!/usr/bin/env -S python3 -u
"""Main session Write/Edit/Bash blocking guard Hook script.

In the PreToolUse(Write|Edit|Bash) event, the current session is the workflow session.
If the main session is not (_WF_SESSION_TYPE=workflow or P:T-*tmux window)
Block code modification.
Blocks even in non-workflow environments.
For Bash tools, only commands containing file modification patterns are blocked.

Session identification is delegated to session_identifier.get_session_type().

Whitelist Policy:
    - .agent-factory/.version: Modification is also allowed in the main session.
    - User memory directory (~/.claude/projects/<encoded>/memory/**):
      An auto memory area unrelated to the code and outside the guard range.
      If Write/Edit file_path is under a memory directory, it passes immediately.
      In a Bash command, if only the memory path argument is targeted and the code path is not included, it passes.
      Blocking preservation (conservative branching) when memory paths and code paths are mixed.

Main functions:
    main: Hook entry point, blocks main session Write/Edit/Bash after parsing stdin JSON

Input: JSON to stdin (tool_name, tool_input)
Output: hookSpecificOutput JSON when blocking, empty output when passing.

Toggle: Environment variable HOOK_MAIN_SESSION_GUARD (false/0 = disabled, default enabled)
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
from flow.session_identifier import get_session_type
from messages import (
    MAIN_SESSION_BASH_FILE_MODIFY_DENIED,
    MAIN_SESSION_NO_TMUX_DENIED,
    MAIN_SESSION_WRITE_EDIT_DENIED,
)

# Command patterns that allow Bash tools to modify files (blacklist)
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

# User memory directory pattern: ~/.claude/projects/<encoded>/memory/** matching
# <encoded> is dash-encoding form (e.g. -home-deus-workspace-claude)
_MEMORY_DIR_PATTERN: re.Pattern[str] = re.compile(
    r"(?:^|/)\.claude/projects/[^/]+/memory(?:/|$)"
)

# Keep blocking when Bash memory whitelists: code path patterns
_CODE_PATH_PATTERN: re.Pattern[str] = re.compile(
    r"board/|engine/|hooks/|\.agent-factory/"
)


def _is_memory_path(path: str) -> bool:
    """Check whether the file path is under the user memory directory.

    Matches ~/.claude/projects/<encoded>/memory/ or its subpath.
    Convert ~ to an absolute path with os.path.expanduser and check the pattern.

    Args:
        path: File path to check (absolute path or ~start path)

    Returns:
        True if it is a subpath of the memory directory, False otherwise.
    """
    if not path:
        return False
    expanded = os.path.expanduser(path)
    return bool(_MEMORY_DIR_PATTERN.search(expanded))


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


def _strip_quoted_args(command: str) -> str:
    """Replaces the contents of the area surrounded by quotation marks in the command string with an empty string.

    By removing text inside single quotes ('...') and double quotes ("..."),
    Even if the argument value contains dangerous command text, the pattern matching target
    Preprocess to exclude. Escaped quotation marks (\\", \\') are quotation marks.
    It is not recognized as an end.

    Args:
        command: Original command string from Bash tool

    Returns:
        A string with the content inside the quotes removed. The quotation marks themselves are preserved.
    """
    # Double quotes: Skip escaped \" and replace content with empty string
    command = re.sub(r'"(?:[^"\\]|\\.)*"', '""', command)
    # Single quote: Skip escaped \' and replace content with empty string
    command = re.sub(r"'(?:[^'\\]|\\.)*'", "''", command)
    return command


def _extract_command_positions(command: str) -> list[str]:
    """Splits the command string by the pipe/chain delimiter and returns a list of segments.

    The command string after the strip quotes is pipe (|), semicolon (;), AND (&&),
    Split with OR(||) delimiter. By removing leading spaces from each segment,
    Ensure that the command token is at the start of the segment.

    Splitting order: &&, || are processed first, followed by |, ; Divide in order.
    single | is || To distinguish it from , it matches with the pattern (?<!|)\\|(?!|).

    Args:
        command: command string complete with quoted strip

    Returns:
        A list of strings with leading spaces removed from each segment.
        Empty string segments are excluded.
    """
    # &&, ||, single |, ; Split by delimiter (treat || before |)
    parts = re.split(r'&&|\|\||(?<!\|)\|(?!\|)|;', command)
    return [part.lstrip() for part in parts if part.strip()]


def _check_bash_file_modify(command: str) -> None:
    """Bash commands check file modification patterns and block when matching.

    First remove the argument area surrounded by quotes (_strip_quoted_args), then
    Split segments by pipe/chain separator (_extract_command_positions)
    Check the _BASH_FILE_MODIFY_PATTERNS pattern in each segment.
    If at least one match is made, _deny() is called.
    If it does not match, it passes through sys.exit(0).

    Args:
        command: Command string of Bash tool
    """
    stripped = _strip_quoted_args(command)
    segments = _extract_command_positions(stripped)
    for segment in segments:
        for pattern in _BASH_FILE_MODIFY_PATTERNS:
            if re.search(pattern, segment):
                _deny(MAIN_SESSION_BASH_FILE_MODIFY_DENIED.format(pattern=pattern))
    # Pass if there is no file modification pattern
    sys.exit(0)


def main() -> None:
    """Main session Write/Edit/Bash blocking Hook entry point.

    When using Write/Edit/Bash tools by reading JSON from stdin, the current session
    Check if it is a workflow session, and if it is a main session, output a deny response
    Block code modification.
    Session identification is delegated to session_identifier.get_session_type().
    For Bash tools, only commands containing file modification patterns are blocked.
    """
    # Load settings from .agent-factory/.settings
    hook_flag = os.environ.get("HOOK_MAIN_SESSION_GUARD") or read_env("HOOK_MAIN_SESSION_GUARD")

    # Hook disable check (false = disabled)
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

    # .agent-factory/.version files can also be modified in the main session.
    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    if file_path.endswith(".agent-factory/.version"):
        sys.exit(0)

    # Memory Directory Whitelist: Write/Edit tools immediately pass anything below a memory path.
    if tool_name in ("Write", "Edit") and _is_memory_path(file_path):
        sys.exit(0)

    # Determine session type (delegated to session_identifier)
    session_type = get_session_type()

    # Passes if it is a workflow session.
    if session_type == "workflow":
        sys.exit(0)

    # unknown: Session type determination failed (conservative blocking)
    if session_type == "unknown":
        if tool_name == "Bash":
            command = tool_input.get("command", "")
            # If only the memory path is targeted and the code path is not included, pass (conservative: block if mixed)
            if _MEMORY_DIR_PATTERN.search(command) and not _CODE_PATH_PATTERN.search(command):
                sys.exit(0)
            _check_bash_file_modify(command)
        _deny(MAIN_SESSION_NO_TMUX_DENIED)

    # main session: Bash blocks only file modification patterns
    if tool_name == "Bash":
        command = tool_input.get("command", "")
        # If only the memory path is targeted and the code path is not included, pass (conservative: block if mixed)
        if _MEMORY_DIR_PATTERN.search(command) and not _CODE_PATH_PATTERN.search(command):
            sys.exit(0)
        _check_bash_file_modify(command)

    # Write/Edit is blocked in the main session
    _deny(MAIN_SESSION_WRITE_EDIT_DENIED.format(window_name=session_type))


if __name__ == "__main__":
    main()
