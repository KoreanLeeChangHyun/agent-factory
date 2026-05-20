#!/usr/bin/env -S python3 -u
"""
common.py - project common utility.

project route interpretation, ANSI color code, JSON atomic writing,
Copyright (C) 2018. All Rights Reserved.
We provide a common feature that is used globally.

Tag:
    resolve project root: project route absolute path interpretation
    load json file: JSON file load (unless returns when missing)
    atomic write json: JSON atomic writing
    Scan active workflows: Active Workflow Directory Scan
    resolve active workflow: Current active workflow context return
    resolve work dir: shortcut key to view workDir paths
    resolve abs work dir: workDir absolute path conversion
    read env: .agent-factory/.settings environment variable read
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any

# -- sys.path Warranty: Added scripts/ directory for when this module is running directly --
_engine_dir = os.path.dirname(os.path.abspath(__file__))
if _engine_dir not in sys.path:
    sys.path.insert(0, _engine_dir)

# =============================================================================
# import from data.constants (re-export to lower compatibility)
# =============================================================================
from constants import (  # noqa: E402
    C_RED,
    C_BLUE,
    C_GREEN,
    C_PURPLE,
    C_YELLOW,
    C_CYAN,
    C_GRAY,
    C_CLAUDE,
    C_BOLD,
    C_DIM,
    C_RESET,
    STEP_COLORS,
    PHASE_COLORS,  # Re-export
    TS_PATTERN,
)


def _detect_worktree_main_root(base: str) -> str:
    """Return to the main project route in accordance with the work tree.

    git rev-parse --git-common-dir
    If the parent directory is different from the base, it is judged inside the work tree.
    returns the main repository root.

    Args:
        base: Candidate project route (end route).

    Returns:
        Main project route absolute path. git failure or worktree or base return.
    """
    # . If you have agent-factory/.settings, you already need to call git
    cw_dir = os.path.join(base, ".agent-factory")
    if os.path.exists(os.path.join(cw_dir, ".settings")):
        return base

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=base,
        )
        if result.returncode == 0:
            git_common = result.stdout.strip()
            # git-common-dir points the main repository .git directory
            main_root = os.path.dirname(git_common)
            if main_root != base:
                return main_root
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    return base


def resolve_project_root(start_path: str | None = None) -> str:
    """Project route interpretation.

    utils -> scripts -> .claude -> navigate the top directory in the project root order
    We will determine the project route. The main repo even if it is called inside worktree
    <# if ( data.meta.album ) { #>{{ data.meta.album }}<# } #>

    Args:
        start path: navigation start path. If None, the location of this file.

    Returns:
        Skip to main content
    """
    if start_path:
        base = os.path.abspath(start_path)
    else:
        # scripts -> .claude -> project root
        scripts_dir = os.path.dirname(os.path.abspath(__file__))
        base = os.path.normpath(os.path.join(scripts_dir, "..", ".."))
    return _detect_worktree_main_root(base)


def load_json_file(path: str) -> Any | None:
    """Load JSON file. None returns when failed.

    Args:
        path: JSON file path.

    Returns:
        parsed JSON data. None if there is no file or parsing failure.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError, OSError):
        return None


def atomic_write_json(path: str, data: Any, indent: int = 2) -> None:
    """JSON atomic writing (temp file + mv).

    Write JSON in a temporary file and moves to the target path at all times.

    Args:
        path: write target file path.
        data: JSON serialized data.
        indent: JSON indent level. Default 2.

    Raises:
        Exception: When writing fails. Send your inquiry directly to us
    """
    dir_name = os.path.dirname(path)
    os.makedirs(dir_name, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=indent)
            f.write("\n")
        shutil.move(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def extract_registry_key(work_dir: str) -> str:
    """The registry key extraction in YYYMMDD-HMMSS format in the workDir path.

    Tag: /<YYYYMMDD-HMMSS>/<workName>/<command>
    Legacy Flat Frame: ... /<YYYYMMDD-HMMSS>

    Args:
        work dir: workflow directory path.

    Returns:
        YYYYMMDD-HMMSS format key. return basename when pattern matches.
    """
    basename = os.path.basename(work_dir)
    if TS_PATTERN.match(basename):
        return basename

    # nest structure: basename=<command>, parent=<workName>, grandparent=<YYYYMMDD-HMMSS>
    grandparent = os.path.basename(os.path.dirname(os.path.dirname(work_dir)))
    if TS_PATTERN.match(grandparent):
        return grandparent

    # Poly bag: YYYMMDD-HMMSS pattern navigation on the path
    parts = work_dir.replace(os.sep, "/").split("/")
    for part in parts:
        if TS_PATTERN.match(part):
            return part

    # Knitwear
    return basename


def scan_active_workflows(
    project_root: str | None = None,
    include_terminal: bool = False,
) -> dict[str, dict[str, str]]:
    """. Scan the agent-factory/runs/ directory to return the workflow list.

    T-449 Pole Structure: .agent-factory/runs/<YYYYMMDD-HMMSS>/ In Straight
    return status.json and .context.json in dict format.

    Args:
        project root: project route. Automatic interpretation if None.
        include terminal: Includes True DONE/FAILED/STALE/CANCELLED.

    Returns:
        딕셔너리   볶음밥헌터
        Each value is {"title", "step", "workDir", "command"} format.
        If you don’t have an active workflow, you’ll be blank.
    """
    if project_root is None:
        project_root = resolve_project_root()

    from constants import TERMINAL_PHASES

    workflow_root = os.path.join(project_root, ".agent-factory", "runs")
    if not os.path.isdir(workflow_root):
        return {}

    result: dict[str, dict[str, str]] = {}
    for entry in os.listdir(workflow_root):
        if not TS_PATTERN.match(entry):
            continue
        entry_path = os.path.join(workflow_root, entry)
        if not os.path.isdir(entry_path):
            continue

        status_file = os.path.join(entry_path, "status.json")
        if not os.path.isfile(status_file):
            continue
        context_file = os.path.join(entry_path, ".context.json")

        status = load_json_file(status_file)
        # T-483 Settlement: status.json's phase key is `workflow phase` (T-453 New).
        # The old key `step` / `phase` subhormonal foldback.
        if isinstance(status, dict):
            phase = (
                status.get("workflow_phase")
                or status.get("step")
                or status.get("phase")
                or "NONE"
            )
        else:
            phase = "NONE"

        if not include_terminal and phase in TERMINAL_PHASES:
            continue

        ctx = load_json_file(context_file)
        title = ctx.get("title", "") if isinstance(ctx, dict) else ""
        command = ctx.get("command", "") if isinstance(ctx, dict) else ""

        rel_work_dir = os.path.join(".agent-factory", "runs", entry)
        result[entry] = {
            "title": title,
            "step": phase,
            "workDir": rel_work_dir,
            "command": command,
        }

    return result


def _get_workflow_updated_at(project_root: str, entry: dict[str, str]) -> str:
    """read updated at in workflow status.json.

    Args:
        project root: project route absolute path.
        entry: workflow entries containing workDir keys.

    Returns:
        updated at string. empty string without status.json or key.
    """
    work_dir = entry.get("workDir", "")
    abs_wd = (
        os.path.join(project_root, work_dir)
        if not os.path.isabs(work_dir)
        else work_dir
    )
    status = load_json_file(os.path.join(abs_wd, "status.json"))
    if status:
        return status.get("updated_at", "")
    return ""


def _select_by_most_recent(
    candidates: list[tuple[str, dict[str, str]]],
    project_root: str,
) -> tuple[str | None, dict[str, str] | None]:
    """The most recent workflow selection based on updated at.

    Args:
        candidates: (registryKey, entry) tuple list.
        project root: project route absolute path.

    Returns:
        (registryKey, entry) tuple. No candidate (None, None).
    """
    with_time: list[tuple[str, dict[str, str], str]] = []
    for key, entry in candidates:
        updated_at = _get_workflow_updated_at(project_root, entry)
        with_time.append((key, entry, updated_at))
    if not with_time:
        return None, None
    with_time.sort(key=lambda x: x[2], reverse=True)
    return with_time[0][0], with_time[0][1]


def resolve_active_workflow(project_root: str | None = None) -> dict[str, str] | None:
    """Query return by identifying active workflows with directory scanning.

    If single workflow, select immediately, revenge PLAN step first,
    If the same condition is updated at, select as the latest.

    Args:
        project root: project route. Automatic interpretation if None.

    Returns:
        Active workflow context idiaries {"title", "workId", "workName",
        "command", "agent", "step"}. None without an active workflow.
    """
    if project_root is None:
        project_root = resolve_project_root()

    registry = scan_active_workflows(project_root=project_root)

    if not isinstance(registry, dict) or not registry:
        return None

    entries = [(k, v) for k, v in registry.items() if isinstance(v, dict)]
    if not entries:
        return None

    selected_entry: dict[str, str] | None = None

    if len(entries) == 1:
        _, selected_entry = entries[0]
    else:
        plan_entries = [
            (k, v) for k, v in entries if v.get("step", "") == "PLAN"
        ]
        if len(plan_entries) == 1:
            _, selected_entry = plan_entries[0]
        elif len(plan_entries) > 1:
            _, selected_entry = _select_by_most_recent(plan_entries, project_root)
        else:
            _, selected_entry = _select_by_most_recent(entries, project_root)

    if not selected_entry:
        return None

    # . context.json load
    work_dir = selected_entry.get("workDir", "")
    abs_work_dir = (
        os.path.join(project_root, work_dir)
        if not os.path.isabs(work_dir)
        else work_dir
    )
    ctx = load_json_file(os.path.join(abs_work_dir, ".context.json"))
    if not ctx:
        return None

    title = ctx.get("title", "")
    work_id = ctx.get("workId", "")
    work_name = ctx.get("workName", "") or ctx.get("title", "")
    command = ctx.get("command", "")
    agent = ctx.get("agent", "")

    if not (title and work_id and command):
        return None

    # read step in status.json
    status = load_json_file(os.path.join(abs_work_dir, "status.json"))
    phase = (status.get("step") or status.get("phase", "")) if status else ""

    return {
        "title": title,
        "workId": work_id,
        "workName": work_name,
        "command": command,
        "agent": agent,
        "step": phase,
    }


def resolve_work_dir(input_key: str, project_root: str | None = None) -> str:
    """YYYYMMDD-HMMSS short format key to workDir directory scan view.

    YYYYMMDD-HMMSS not pattern input is returned.

    Tag:
      1. .agent-factory/runs/<input key>/status.json
      2. FAQ .agent-factory/runs/.history/<input key>/status.json
      3. FAQs ".agent-factory/runs/<input key>" returns poly bag when both navigation fails.

    Args:
        input key: workflow key (YYYYMMDD-HMMSS) or path.
        project root: project route. Automatic interpretation if None.

    Returns:
        interpreted workDir relative path. ".agent-factory/runs/<input key>" foldback when scanning failed.
    """
    if not TS_PATTERN.match(input_key):
        return input_key

    if project_root is None:
        project_root = resolve_project_root()

    def _scan_base(base: str, rel_prefix: str) -> str | None:
        """T-448 pod structure: return rel prefix when the base/status.json exists."""
        if not os.path.isdir(base):
            return None

        if os.path.exists(os.path.join(base, "status.json")):
            return rel_prefix

        return None

    # Primary navigation: Active workflow directory
    base_dir = os.path.join(project_root, ".agent-factory", "runs", input_key)
    result = _scan_base(base_dir, os.path.join(".agent-factory", "runs", input_key))
    if result is not None:
        return result

    # 2nd navigation: .history/ archive directory
    history_base_dir = os.path.join(project_root, ".agent-factory", "runs", ".history", input_key)
    result = _scan_base(history_base_dir, os.path.join(".agent-factory", "runs", ".history", input_key))
    if result is not None:
        return result

    # Paul White
    fallback = f".agent-factory/runs/{input_key}"
    print(
        f"[WARN] directory scan failed for {input_key}, falling back to {fallback}",
        file=sys.stderr,
    )
    return fallback


def resolve_abs_work_dir(work_dir: str, project_root: str | None = None) -> str:
    """Convert workDir to absolute paths.

    YYYYMMDD-HMMSS shortcode format converts to absolute path after searching with directory scanning.
    Configuring the absolute path based on project root.

    Args:
        work dir: workflow directory path. Short-term/horizontal formats are accepted.
        project root: project route. Automatic interpretation if None.

    Returns:
        absolute path string.
    """
    if project_root is None:
        project_root = resolve_project_root()

    # Skip to content
    if TS_PATTERN.match(work_dir):
        work_dir = resolve_work_dir(work_dir, project_root)

    # Skip to content
    if os.path.isabs(work_dir):
        return work_dir
    return os.path.join(project_root, work_dir)


# =============================================================================
# Environmental Modulation (.agent-factory/.settings)
# =============================================================================

_DEFAULT_ENV_FILE = os.environ.get("ENV_FILE", "")


def _resolve_env_file(env_file: str | None = None) -> str:
    """interpret the env file path.

    If none, you will be enrolled in the environment variable or project route.
    Args:
        env file: .agent-factory/.settings file path. Automatic interpretation if None.

    Returns:
        interpreted env file absolute path string.
    """
    if env_file:
        return env_file
    if _DEFAULT_ENV_FILE:
        return _DEFAULT_ENV_FILE
    scripts_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.normpath(os.path.join(scripts_dir, "..", ".."))
    return os.path.join(project_root, ".agent-factory", ".settings")


def read_env(key: str, default: str = "", env_file: str | None = None) -> str:
    """. Read environment variables in agent-factory/.settings.

    Duplicate key defense (first matching), eliminating quotes, including $HOME/~ extensions.

    Args:
        key: environment variable key name.
        default: The default to return when the key is not.
        env file: .agent-factory/.settings file path. Automatic interpretation if None.

    Returns:
        Environment variable value. If there is no file or no key, the default return.
    """
    resolved = _resolve_env_file(env_file)
    if not resolved or not os.path.isfile(resolved):
        return default

    prefix = f"{key}="
    try:
        with open(resolved, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped.startswith(prefix):
                    value = stripped[len(prefix):]
                    if len(value) >= 2:
                        if (value[0] == '"' and value[-1] == '"') or \
                           (value[0] == "'" and value[-1] == "'"):
                            value = value[1:-1]
                    home = os.environ.get("HOME", "")
                    if home:
                        value = value.replace("$HOME", home)
                        if value.startswith("~"):
                            value = home + value[1:]
                    return value
    except (IOError, OSError):
        pass

    return default


# =============================================================================
# Filesystem Lock (mkdir-based POSIX lock)
# =============================================================================


def acquire_lock(lock_dir: str, max_wait: int = 2, stale_timeout: int = 300) -> bool:
    """Mkdir-based POSIX lock. Includes stale lock detection and orphan lock recovery.

    Create a directory and record the owner as a PID file.
    The process is terminated or removed and retry stale locks when exceeding stale timeout seconds.
    orphan lock without pid file immediately recovers and prevents permanent contact.

    Args:
        lock dir: Lock directory path.
        max wait: maximum wait seconds. Default 2.
        stale timeout: stale lock equation value(sec). Exceed this time after creating a lock
            returns to be considered as stale lock. default 300 (5 minutes). Independently with max wait
            so long time merge is also maintained with normal lock.

    Returns:
        Whether it’s a lock acquisition success.
    """
    waited = 0
    while True:
        try:
            os.makedirs(lock_dir)
            try:
                with open(os.path.join(lock_dir, "pid"), "w") as f:
                    f.write(f"{os.getpid()} {time.time()}")
            except OSError:
                pass
            return True
        except OSError:
            pid_file = os.path.join(lock_dir, "pid")
            if not os.path.isfile(pid_file):
                # orphan lock without pid file: retry immediately after recovery
                try:
                    shutil.rmtree(lock_dir)
                except OSError:
                    pass
                continue
            if os.path.isfile(pid_file):
                try:
                    with open(pid_file, "r") as f:
                        pid_content = f.read().strip()
                    parts = pid_content.split()
                    lock_pid = int(parts[0])
                    lock_ts = float(parts[1]) if len(parts) > 1 else 0
                    os.kill(lock_pid, 0)
                    if lock_ts and (time.time() - lock_ts) > stale_timeout:
                        try:
                            with open(pid_file, "r") as f:
                                recheck = f.read().strip()
                            if recheck == pid_content:
                                shutil.rmtree(lock_dir)
                                waited += 1
                                continue
                        except OSError:
                            pass
                except (ValueError, ProcessLookupError, OSError):
                    try:
                        with open(pid_file, "r") as f:
                            recheck = f.read().strip()
                        if recheck == pid_content:
                            shutil.rmtree(lock_dir)
                    except OSError:
                        pass
                    waited += 1
                    continue
                except PermissionError:
                    pass
            waited += 1
            if waited >= max_wait:
                return False
            time.sleep(1)


def release_lock(lock_dir: str) -> None:
    """Unlock.

    Remove the lock directory after removing the PID file.
    The filesystem error is ignored.

    Args:
        lock dir: Unlock directory path.
    """
    try:
        pid_file = os.path.join(lock_dir, "pid")
        if os.path.exists(pid_file):
            os.unlink(pid_file)
    except OSError:
        pass
    try:
        os.rmdir(lock_dir)
    except OSError:
        pass
