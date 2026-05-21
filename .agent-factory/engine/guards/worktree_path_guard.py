#!/usr/bin/env -S python3 -u
"""Worktree path isolation guard Hook script.

In the PreToolUse(Write|Edit|MultiEdit|NotebookEdit|Bash) event, the current session
If it is a workflow session and the command of the active workflow is implement,
Attempts to modify the main repo path file are blocked and the worktree absolute path is included in the feedback.

When Claude Code starts a session, it determines the project root (main repo) as cwd.
Problem of attempting to modify a file based on the main repo path instead of the worktree path
It is a defense-in-depth layer that blocks at the PreToolUse hook layer.

Main functions:
    main: Hook entry point, blocks modification of main repo path after parsing stdin JSON

Input: JSON to stdin (tool_name, tool_input)
Output: hookSpecificOutput JSON when blocking, empty output when passing.

Toggle: Environment variable HOOK_WORKTREE_PATH_GUARD (false/0 = disabled, default enabled)
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
    WORKTREE_PATH_BASH_MODIFY_DENIED,
    WORKTREE_PATH_WRITE_EDIT_DENIED,
)

# implement command: Command to which worktree isolation is applied
_IMPLEMENT_COMMAND = "implement"

# Command pattern that allows Bash tools to modify files (same as readonly_session_guard.py)
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

# Path patterns always allowed (main repo output/sidecar directories)
# Caution: Conservatively narrow definitions — things like `.agent-factory/board/server/`, `.agent-factory/engine/`
_ALWAYS_ALLOWED_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"[/\\]\.agent-factory[/\\]runs[/\\]"),
    re.compile(r"[/\\]\.agent-factory[/\\]board[/\\]sessions[/\\]"),
    re.compile(r"[/\\]\.agent-factory[/\\](?:catalog|kanban|history|sessions)[/\\]"),
]


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

    1. WORKFLOW_COMMAND environment variable takes priority (directly injected by the launcher when a worker spawns — race-free).
    2. WORKFLOW_WORK_DIR environment variable → .context.json.
    3. Scan the .workflow/ directory for the most recent .context.json.

    Returns:
        command string. None if search fails.
    """
    # 1. WORKFLOW_COMMAND environment variable priority (blocks disk scan race)
    env_command = os.environ.get("WORKFLOW_COMMAND", "").strip()
    if env_command:
        return env_command

    project_root = resolve_project_root()

    # 2. Check the WORKFLOW_WORK_DIR environment variable
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

    # 3. Scan the .workflow/ directory
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


def _get_worktree_path() -> str | None:
    """Returns the absolute path to the work tree of the current workflow session.

    Search the worktree path in the following order:
    1. WORKFLOW_WORKTREE_PATH environment variable
    2. WORKFLOW_WORK_DIR environment variable -> .context.json -> worktree.absPath
    3. Scan .workflow/ directory -> .context.json -> worktree.absPath

    Returns:
        Worktree absolute path string. None if navigation fails or no route exists.
    """
    # 1. WORKFLOW_WORKTREE_PATH environment variable takes precedence
    env_worktree_path = os.environ.get("WORKFLOW_WORKTREE_PATH", "").strip()
    if env_worktree_path:
        return env_worktree_path

    project_root = resolve_project_root()

    # 2. WORKFLOW_WORK_DIR environment variable -> .context.json
    env_work_dir = os.environ.get("WORKFLOW_WORK_DIR", "").strip()
    if env_work_dir:
        abs_work_dir = (
            os.path.join(project_root, env_work_dir)
            if not os.path.isabs(env_work_dir)
            else env_work_dir
        )
        ctx = load_json_file(os.path.join(abs_work_dir, ".context.json"))
        if ctx and isinstance(ctx, dict):
            worktree = ctx.get("worktree", {})
            if isinstance(worktree, dict):
                abs_path = worktree.get("absPath", "").strip()
                if abs_path:
                    return abs_path

    # 3. Scan the .workflow/ directory
    try:
        registry = scan_active_workflows(project_root=project_root)
        if not registry:
            return None

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
            work_dir = best_entry.get("workDir", "")
            abs_wd = (
                os.path.join(project_root, work_dir)
                if not os.path.isabs(work_dir)
                else work_dir
            )
            ctx = load_json_file(os.path.join(abs_wd, ".context.json"))
            if ctx and isinstance(ctx, dict):
                worktree = ctx.get("worktree", {})
                if isinstance(worktree, dict):
                    abs_path = worktree.get("absPath", "").strip()
                    if abs_path:
                        return abs_path
    except Exception:
        pass

    return None


def _is_always_allowed_path(file_path: str, project_root: str | None = None) -> bool:
    """Make sure the file path is always an allowed path.

    `_ALWAYS_ALLOWED_PATTERNS` is the main repo output/sidecar directory pattern,
    In the case of a relative path, it is converted to an absolute path based on `project_root` and then matched.

    Args:
        file_path: File path to check (absolute or relative)
        project_root: Absolute path to main repo (used for relative path normalization)

    Returns:
        True if the path is always allowed.
    """
    if not os.path.isabs(file_path) and project_root:
        target = os.path.normpath(os.path.join(project_root, file_path))
    else:
        target = os.path.normpath(file_path)
    for pattern in _ALWAYS_ALLOWED_PATTERNS:
        if pattern.search(target):
            return True
    return False


def _is_under_worktree(
    file_path: str,
    worktree_path: str,
    project_root: str | None = None,
) -> bool:
    """Check whether the file path is under the worktree path.

    If it is a relative path, make it an absolute path based on `project_root` and compare it with the work tree prefix.

    Args:
        file_path: File path to check (absolute or relative)
        worktree_path: Worktree absolute path
        project_root: Absolute path to main repo (used for relative path normalization)

    Returns:
        True if it is a worktree subpath.
    """
    norm_worktree = os.path.normpath(worktree_path)
    if os.path.isabs(file_path):
        norm_file = os.path.normpath(file_path)
    elif project_root:
        norm_file = os.path.normpath(os.path.join(project_root, file_path))
    else:
        return False
    return norm_file.startswith(norm_worktree + os.sep) or norm_file == norm_worktree


def _get_suggested_path(file_path: str, project_root: str, worktree_path: str) -> str:
    """Converts the main repo path to a path in the work tree and returns it.

    Args:
        file_path: Original file path
        project_root: Absolute path to main repo
        worktree_path: Worktree absolute path

    Returns:
        Path string in the worktree.
    """
    norm_project = os.path.normpath(project_root)
    norm_file = os.path.normpath(file_path) if os.path.isabs(file_path) else file_path

    if os.path.isabs(norm_file) and norm_file.startswith(norm_project + os.sep):
        rel = norm_file[len(norm_project) + 1:]
        return os.path.join(worktree_path, rel)

    # If the path is relative, bind directly to the worktree path.
    return os.path.join(worktree_path, file_path.lstrip("/"))


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


def _bash_targets_main_repo(command: str, project_root: str, worktree_path: str) -> bool:
    """Check whether the Bash command attempts to modify files targeting the main repo path.

    Check all occurrences of the main repo absolute path in the command string,
    Passes if each occurrence is a worktree prefix or output/sidecar pattern.
    Others (direct hits to the main source path) are blocked. cross-tree copy
    (`cp /worktree/foo.py /main/.agent-factory/board/server/app.py`)
    Regressions that bypass worktree paths due to simultaneous appearance are blocked using finditer-based prefix inspection.

    Args:
        command: Command string of Bash tool
        project_root: Absolute path to main repo
        worktree_path: Worktree absolute path

    Returns:
        True if the modification targets the main repo path.
    """
    norm_project = os.path.normpath(project_root)
    norm_worktree = os.path.normpath(worktree_path)

    if norm_project not in command:
        return False

    for match in re.finditer(re.escape(norm_project), command):
        start = match.start()
        tail = command[start:]
        if tail.startswith(norm_worktree):
            continue  # Worktree prefix → Tasks within the worktree
        if any(p.search(tail) for p in _ALWAYS_ALLOWED_PATTERNS):
            continue  # Main output/sidecar pattern → Allow
        return True  # Direct hit to main source path → blocked
    return False


def main() -> None:
    """Entry point of the worktree path isolation guard Hook.

    When using Write/Edit/MultiEdit/NotebookEdit/Bash tools by reading JSON from stdin
    If the current session is a workflow implement session and the worktree is set,
    Blocks modification of the main repo path file and guides the work tree path.

    It passes in non-tmux environments, main sessions, research/review sessions, and sessions without worktrees.
    Output/sidecar paths matching `_ALWAYS_ALLOWED_PATTERNS` are always allowed.
    """
    # Load settings from .agent-factory/.settings
    hook_flag = os.environ.get("HOOK_WORKTREE_PATH_GUARD") or read_env("HOOK_WORKTREE_PATH_GUARD")

    # Hook disable check (false/0 = disabled)
    if hook_flag in ("false", "0"):
        sys.exit(0)

    # Reading JSON from stdin
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    tool_name = data.get("tool_name", "")

    # Pass if the tool is not being checked
    if tool_name not in ("Write", "Edit", "MultiEdit", "NotebookEdit", "Bash"):
        sys.exit(0)

    # Check session type -- pass if not workflow session (not a concern of this guard)
    session_type = get_session_type()
    if session_type != "workflow":
        sys.exit(0)

    # --- Workflow session confirmed, command determination ---

    command = _get_workflow_command()

    # When command search fails: If WORKFLOW_WORKTREE_PATH is injected, implement is assumed.
    # Otherwise, pass (avoid false positives)
    if command is None:
        if os.environ.get("WORKFLOW_WORKTREE_PATH", "").strip():
            command = _IMPLEMENT_COMMAND
        else:
            sys.exit(0)

    # Extract the first segment of the command (support chain command: "research>implement" -> "research")
    first_segment = command.split(">")[0].strip()

    # Passes unless it is an implement command (readonly_session_guard is in charge of research/review)
    if first_segment != _IMPLEMENT_COMMAND:
        sys.exit(0)

    # --- implement command confirmed, work tree path search ---

    worktree_path = _get_worktree_path()

    # Passes if there is no worktree path (non-worktree implement session)
    if not worktree_path:
        sys.exit(0)

    # --- Worktree path confirmed, file path checked ---

    project_root = resolve_project_root()
    tool_input = data.get("tool_input", {})

    if tool_name in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        if tool_name == "NotebookEdit":
            file_path = tool_input.get("notebook_path", "")
        else:
            file_path = tool_input.get("file_path", "")
        if not file_path:
            sys.exit(0)

        # Always allow path (main output/sidecar) to pass
        if _is_always_allowed_path(file_path, project_root):
            sys.exit(0)

        # Pass if it is a worktree subpath.
        if _is_under_worktree(file_path, worktree_path, project_root):
            sys.exit(0)

        # In case of a relative path: Paths relative to the main repo root cannot be passed.
        # (Relative path = main repo path since Claude Code uses main repo root as cwd)
        suggested_path = _get_suggested_path(file_path, project_root, worktree_path)
        _deny(
            WORKTREE_PATH_WRITE_EDIT_DENIED.format(
                worktree_path=worktree_path,
                file_path=file_path,
                suggested_path=suggested_path,
            )
        )

    if tool_name == "Bash":
        bash_cmd = tool_input.get("command", "")
        if not bash_cmd:
            sys.exit(0)

        # Pass if there is no file modification pattern
        if not _is_bash_file_modify(bash_cmd):
            sys.exit(0)

        # Block modifications that target the main repo absolute path.
        if _bash_targets_main_repo(bash_cmd, project_root, worktree_path):
            _deny(
                WORKTREE_PATH_BASH_MODIFY_DENIED.format(
                    worktree_path=worktree_path,
                )
            )
        sys.exit(0)

    # Unknown tool: Passed
    sys.exit(0)


if __name__ == "__main__":
    main()
