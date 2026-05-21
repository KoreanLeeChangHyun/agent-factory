"""flow logger.py - Workflow common logging utility.

INFO/WARN/ERROR
We provide a common function.

Tag:
    [YYYY-MM-DDTHH:MM:SS] [LEVEL] message

Tag:
    from flow.flow_logger import append_log, resolve_work_dir_for_logging

    # If you know abs_work_dir directly:
    append_log("/path/to/workdir", "INFO", "conveyor.py: subcommand=list")
    append_log("/path/to/workdir", "WARN", "conveyor.py: No work_request file")
    append_log("/path/to/workdir", "ERROR", "conveyor.py: ERROR state transition failed")

    # If abs_work_dir is unknown (script called outside of workflow)
    work_dir = resolve_work_dir_for_logging()
    if work_dir:
        append_log(work_dir, "INFO", "script: start")

Information:
    - append log() quietly absorbs all exceptions. Configuring the Script
      It does not affect normal execution.
    - resolve work dir for logging() returns None in case of interpretation.
      The caller must skip the logging when the None return.
    - Use KST (UTC+9) standard timestamp.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from typing import Optional

# KST (UTC+9)
_KST = timezone(timedelta(hours=9))

# YYYYMMDD-HHMMSS pattern (registryKey)
_TS_PATTERN = re.compile(r"^\d{8}-\d{6}$")


def append_log(abs_work_dir: str, level: str, message: str) -> None:
    """Create an event in a workflow log file.

    Add the log with KST timestamp to workflow.log file.
    We use cookies to give you the best experience on our website. If you continue to use this site we will assume that you are happy with it.Ok

    Args:
        abs work dir: workflow absolute path. directory where workflow.log is located.
        level: log level. "INFO", "WARN", "ERROR".
        message: log message.

    Tag:
        [YYYY-MM-DDTHH:MM:SS] [LEVEL] message
    """
    try:
        ts = datetime.now(_KST).strftime("%Y-%m-%dT%H:%M:%S")
        log_path = os.path.join(abs_work_dir, "workflow.log")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] [{level}] {message}\n")
    except Exception:
        pass


def resolve_work_dir_for_logging(
    project_root: Optional[str] = None,
) -> Optional[str]:
    """returns the abs work dir in the current active workflow.

    interpret abs work dir in the following order NEWS
    1. FAQ Environment variable WORKFLOW WORK DIR (Direct)
    2. FAQ WORKFLOW REGISTRY KEY + KEY Scan
    3. FAQs .workflow/Director Scan (Single Acting Workflow Automatic)

    Returns None in case of interpretation. The caller skips the logging when the None return.

    Args:
        project root: project route absolute path. Automatic interpretation if None.

    Returns:
        abs work dir absolute path string. None.
    """
    try:
        if project_root is None:
            project_root = _resolve_project_root()

        # 1. Directly specify the environment variable WORKFLOW_WORK_DIR
        env_work_dir = os.environ.get("WORKFLOW_WORK_DIR", "").strip()
        if env_work_dir:
            if os.path.isabs(env_work_dir):
                if os.path.isdir(env_work_dir):
                    return env_work_dir
            else:
                abs_wd = os.path.join(project_root, env_work_dir)
                if os.path.isdir(abs_wd):
                    return abs_wd

        # 2. Environment variable WORKFLOW_REGISTRY_KEY + directory scan
        registry_key = os.environ.get("WORKFLOW_REGISTRY_KEY", "").strip()
        if registry_key and _TS_PATTERN.match(registry_key):
            resolved = _resolve_work_dir_from_key(registry_key, project_root)
            if resolved:
                return resolved

        # 3. Scan .workflow/ directory (automatically selects single active workflow)
        resolved = _resolve_from_active_workflows(project_root)
        if resolved:
            return resolved

    except Exception:
        pass

    return None


# =============================================================================
# Internal helper function
# =============================================================================


def _resolve_project_root() -> str:
    """The project route will interpret the absolute path.

    .claude -> project root
    Skip to main content (claude/worktrees/agent-*)
    If running on   file   Based 4 step navigation returns the path inside the worktree, so
    git-common-dir

    Returns:
        Skip to main content
    """
    # flow_logger.py Location: <project_root>/.agent-factory/engine/flow/flow_logger.py
    # Subagent worktree location:
    #   <main_root>/.claude/worktrees/agent-*/.agent-factory/engine/flow/flow_logger.py
    this_file = os.path.abspath(__file__)
    flow_dir = os.path.dirname(this_file)          # .agent-factory/engine/flow/
    scripts_dir = os.path.dirname(flow_dir)        # .agent-factory/engine/
    claude_dir = os.path.dirname(scripts_dir)      # .agent-factory/
    candidate = os.path.dirname(claude_dir)        # <candidate>/

    # Main repo root if .agent-factory/.settings exists — returns immediately
    cw_dir = os.path.join(candidate, ".agent-factory")
    if os.path.exists(os.path.join(cw_dir, ".settings")):
        return candidate

    # Could be inside the worktree — browse the main repo with git-common-dir
    # (same pattern as dispatcher.py _find_project_root())
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=candidate,
        )
        if result.returncode == 0:
            git_common = result.stdout.strip()
            # git-common-dir points to the .git directory in the main repo
            main_root = os.path.dirname(git_common)
            main_cw_dir = os.path.join(main_root, ".agent-factory")
            if main_root != candidate and (
                os.path.exists(os.path.join(main_cw_dir, ".settings"))
            ):
                return main_root
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    return candidate


def _resolve_work_dir_from_key(
    registry_key: str, project_root: str
) -> Optional[str]:
    """abs work dir as registryKey is interpreted as a directory scan.

    T-449 handles only the fold structure after migration NEWS
    . workflow/<YYYYMMDD-HMMSS>/status.json — return base dir itself.

    Args:
        registry key: YYYMMDD-HMMSS format registry key.
        project root: project route absolute path.

    Returns:
        abs work dir absolute path. None when interpretation fails.
    """
    base_dir = os.path.join(project_root, ".agent-factory", "runs", registry_key)
    if not os.path.isdir(base_dir):
        return None

    if os.path.exists(os.path.join(base_dir, "status.json")):
        return base_dir

    return None


def _resolve_from_active_workflows(project_root: str) -> Optional[str]:
    """Automatically select abs work dir by scanning an active workflow.

    . DONE/FAILED/STALE/CANCELLED
    Collect workflows. A single active workflow will return immediately.
    If you have multiple CLAUDE SESSION ID environment variables, you can first identify session ownership workflow,
    Returns updated at standard latest items only when matching failed.

    Args:
        project root: project route absolute path.

    Returns:
        abs work dir absolute path. None if there is no active workflow.
    """
    workflow_root = os.path.join(project_root, ".agent-factory", "runs")
    if not os.path.isdir(workflow_root):
        return None

    _TERMINAL_PHASES = {"DONE", "FAILED", "STALE", "CANCELLED"}

    # (abs_work_dir, updated_at, linked_sessions)
    candidates: list[tuple[str, str, list]] = []

    def _collect_candidate(cmd_path: str) -> None:
        """Read cmd_path/status.json and add to candidates if active workflow."""
        status_file = os.path.join(cmd_path, "status.json")
        if not os.path.exists(status_file):
            return

        try:
            with open(status_file, "r", encoding="utf-8") as f:
                status = json.load(f)
        except Exception:
            return

        if not isinstance(status, dict):
            return

        phase = status.get("workflow_phase") or status.get("step") or status.get("phase", "NONE")  # legacy status.json (pre
        if phase in _TERMINAL_PHASES:
            return

        updated_at = status.get("updated_at", "")
        linked_sessions = status.get("linked_sessions", [])
        if not isinstance(linked_sessions, list):
            linked_sessions = []
        candidates.append((cmd_path, updated_at, linked_sessions))

    for entry in sorted(os.listdir(workflow_root)):
        if not _TS_PATTERN.match(entry):
            continue
        entry_path = os.path.join(workflow_root, entry)
        if not os.path.isdir(entry_path):
            continue

        if os.path.exists(os.path.join(entry_path, "status.json")):
            _collect_candidate(entry_path)

    if not candidates:
        return None

    if len(candidates) == 1:
        return candidates[0][0]

    # Multiple candidates: First identify the session-owning workflow by CLAUDE_SESSION_ID.
    # Check the linked_sessions array in the same way as statusline.py.
    claude_sid = os.environ.get("CLAUDE_SESSION_ID", "").strip()
    if claude_sid:
        session_matches = [
            (cmd_path, updated_at)
            for cmd_path, updated_at, linked in candidates
            if claude_sid in linked
        ]
        if len(session_matches) == 1:
            return session_matches[0][0]
        if len(session_matches) > 1:
            # Multiple candidates connected to the same session select the latest based on updated_at
            session_matches.sort(key=lambda x: x[1], reverse=True)
            return session_matches[0][0]

    # If session matching fails, fall back to the latest item based on updated_at
    candidates.sort(key=lambda x: x[1], reverse=True)
    return candidates[0][0]
