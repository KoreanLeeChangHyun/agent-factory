#!/usr/bin/env -S python3 -u
"""hooks directory Self-protection guard Hook script.

Block modification of .agent-factory/hooks/ path file in PreToolUse(Write|Edit|Bash) event.

Main functions:
    main: Hook entry point, blocks protection path modification after parsing stdin JSON

Input: JSON to stdin (tool_name, tool_input)
Output: hookSpecificOutput JSON when blocking, empty output when passing.

Bypass: Unblock when setting the environment variable HOOKS_EDIT_ALLOWED=1
      (The orchestrator turns it on/off with the command `.agent-factory/engine/flow/update_state.py env <registryKey> set HOOKS_EDIT_ALLOWED 1`)
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
from messages import (
    HOOKS_BYPASS_FILE_DENIED,
    HOOKS_BASH_MODIFY_DENIED,
    HOOKS_WRITE_EDIT_DENIED,
)

# Load guard pattern (security first: conservative fallback on import failure)
try:
    from constants import (
        GUARD_READONLY_PATTERNS as READONLY_PATTERNS,
        GUARD_MODIFY_PATTERNS as MODIFY_PATTERNS,
        GUARD_PROTECTED_PATH_PATTERNS as PROTECTED_PATH_PATTERNS,
        GUARD_INLINE_WRITE_PATTERNS as INLINE_WRITE_PATTERNS,
    )
    PROTECTED_PATH_RES: list[re.Pattern[str]] = [re.compile(p) for p in PROTECTED_PATH_PATTERNS]
except ImportError:
    print(
        "[hooks_self_guard] CRITICAL: data.constants guard patterns import failed - apply security fallback",
        file=sys.stderr,
    )
    READONLY_PATTERNS: list[str] = []
    MODIFY_PATTERNS: list[str] = [r"."]
    PROTECTED_PATH_RES = [re.compile(r"\.claude\.workflow/hooks/"), re.compile(r"\.claude\.workflow/workflow/bypass")]
    INLINE_WRITE_PATTERNS: list[str] = [r"."]


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


def _refs_protected(text: str) -> bool:
    """Verify that the text refers to the protected path.

    Args:
        text: text string to check

    Returns:
        True if matches the protected path pattern, False otherwise.
    """
    for p_re in PROTECTED_PATH_RES:
        if p_re.search(text):
            return True
    return False


def _check_inline_write(subcmd: str) -> bool:
    """Detects writes to protected paths within inline code (-c/-e flags).

    Args:
        subcmd: Subcommand string to check

    Returns:
        True if an inline write pattern is detected, False otherwise.
    """
    if not re.search(r"\s+-(c|e)\s", subcmd):
        return False
    if not _refs_protected(subcmd):
        return False
    for wp in INLINE_WRITE_PATTERNS:
        if re.search(wp, subcmd):
            return True
    return False


def _classify_bash_command(bash_cmd: str) -> str | None:
    """Classifies Bash commands and returns 'READONLY' or 'MODIFY'.

    None (pass) if no protected path is referenced.

    Args:
        bash_cmd: Bash command string to categorize

    Returns:
        'READONLY': if it contains only read-only commands
        'MODIFY': if a modification operation is detected
        None: If no protected path is referenced.
    """
    if not _refs_protected(bash_cmd):
        return None

    # Separate pipeline/connection commands
    subcmds = re.split(r"\s*(?:&&|\|\||[;|])\s*", bash_cmd)
    # $() and backtick internal commands are also extracted
    subcmds += re.findall(r"\$\(([^)]+)\)", bash_cmd)
    subcmds += re.findall(r"\x60([^\x60]+)\x60", bash_cmd)

    for sc in subcmds:
        sc = sc.strip()
        if not sc:
            continue
        if not _refs_protected(sc):
            continue

        # Check if a command is read-only
        is_ro = False
        for ro_pat in READONLY_PATTERNS:
            if re.match(ro_pat, sc):
                is_ro = True
                break

        if is_ro:
            # MODIFY if there is an inline code writing pattern, even if it is read-only
            if _check_inline_write(sc):
                return "MODIFY"
            continue

        # Correction pattern inspection
        for mod_pat in MODIFY_PATTERNS:
            if re.search(mod_pat, sc):
                return "MODIFY"

        # Even if it does not match an explicit modification pattern,
        # Safe blocking if not in read-only whitelist (conservative approach)
        return "MODIFY"

    # All subcommands are read-only or do not reference the protected path
    return "READONLY"


def main() -> None:
    """hooks directory Self-protection guard Entry point for Hook.

    Blocks protection path modification when reading JSON from stdin and executing Write/Edit/Bash tools.
    If the HOOKS_EDIT_ALLOWED environment variable is set, blocking can be bypassed.
    The .agent-factory/runs/bypass path is always blocked without bypassing environment variables.
    """
    # Load settings from .agent-factory/.settings
    hook_flag = os.environ.get("HOOK_HOOKS_SELF_PROTECT") or read_env("HOOK_HOOKS_SELF_PROTECT")
    hook_edit_allowed = os.environ.get("HOOKS_EDIT_ALLOWED") or read_env("HOOKS_EDIT_ALLOWED")

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

    tool_input = data.get("tool_input", {})

    # --- Bash tools branch ---
    if tool_name == "Bash":
        bash_cmd = tool_input.get("command", "")
        if not bash_cmd:
            sys.exit(0)

        # Passes if there is no protected path in the command
        if not _refs_protected(bash_cmd):
            sys.exit(0)

        # Environment variable bypass check
        if hook_edit_allowed in ("true", "1"):
            sys.exit(0)

        classification = _classify_bash_command(bash_cmd)
        if classification == "READONLY":
            sys.exit(0)

        # Branch blocking messages depending on whether .agent-factory/runs/bypass is referenced or not
        if re.search(r"\.claude\.workflow/workflow/bypass", bash_cmd):
            _deny(HOOKS_BYPASS_FILE_DENIED)
        else:
            _deny(HOOKS_BASH_MODIFY_DENIED)

    # --- Write/Edit tools branch ---
    file_path = tool_input.get("file_path", "")
    if not file_path:
        sys.exit(0)

    # Check whether .agent-factory/runs/bypass path is included
    if ".agent-factory/runs/bypass" in file_path:
        # Bypass files cannot bypass environment variables (unconditionally blocked)
        _deny(HOOKS_BYPASS_FILE_DENIED)

    # Check whether .agent-factory/hooks/ path is included
    if ".agent-factory/hooks/" in file_path:
        # Environment variable bypass check
        if hook_edit_allowed in ("true", "1"):
            sys.exit(0)

        _deny(HOOKS_WRITE_EDIT_DENIED)

    # Passes when .agent-factory/hooks/ path does not match.
    sys.exit(0)


if __name__ == "__main__":
    main()
