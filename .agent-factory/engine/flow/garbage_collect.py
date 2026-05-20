#!/usr/bin/env -S python3 -u
"""block collect.py - zombie workflow cleanup standalone script.

Feature:
  1. .workflow/ TTL(24 hours) expiration + unfinished status.json switch to STALE

Usage:
  flow-gc [project_root]

Tag:
  project root - project route (optional). Copyright (c) 2015 ILSHIN TECH. All Rights Reserved.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS_DIR = os.path.normpath(os.path.join(_SCRIPT_DIR, ".."))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from constants import KST, ZOMBIE_TTL_HOURS, TERMINAL_STEPS, TERMINAL_PHASES
from flow.cli_utils import build_common_epilog
from flow.flow_logger import append_log, resolve_work_dir_for_logging

_KST = KST
_TTL_HOURS = ZOMBIE_TTL_HOURS
_TERMINAL_PHASES = TERMINAL_STEPS  # Use TERMINAL_STEPS (TERMINAL_PHASES is an alias)


def _atomic_write_json(path: str, data: object) -> None:
    """After JSON is written in a temporary file, move to the target path.

    Args:
        path: file path to save the end
        data: JSON

    Raises:
        Exception: Eliminate and reissue temporary files when writing or moving failures.
    """
    dir_name = os.path.dirname(path)
    os.makedirs(dir_name, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        shutil.move(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def _process_status_file(status_file: str, status_dir: str, now: datetime) -> bool:
    """Switch status.json to STALE

    Args:
        status file: status.json file path to check
        status dir: directory path where status.json is located
        now: current timezone-aware

    Returns:
        True, otherwise False.
    """
    try:
        with open(status_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        phase = data.get("workflow_phase") or data.get("step") or data.get("phase", "")  # legacy status.json (pre
        if phase in _TERMINAL_PHASES:
            return False

        time_str = data.get("updated_at") or data.get("created_at", "")
        if not time_str:
            return False

        created = datetime.fromisoformat(time_str)
        elapsed = now - created

        if elapsed.total_seconds() > _TTL_HOURS * 3600:
            transition_time = now.strftime("%Y-%m-%dT%H:%M:%S+09:00")
            data["workflow_phase"] = "STALE"
            data["updated_at"] = transition_time
            if "transitions" not in data:
                data["transitions"] = []
            data["transitions"].append({
                "from": phase,
                "to": "STALE",
                "at": transition_time,
            })
            _atomic_write_json(status_file, data)
            return True

        return False
    except (json.JSONDecodeError, IOError, ValueError, TypeError):
        return False


def _step1_mark_stale(workflow_root: str) -> int:
    """Step 1: Switch TTL expiration workflow to STALE in .workflow/ sub.

    T-449 migration since `.workflow/<YYYMMDD-HMMSS>/status.json`
    Polypropylene is only processed. Old nesting structure fallback was removed.

    Args:
        workflow root: .workflow directory absolute path

    Returns:
        STALE
    """
    if not os.path.isdir(workflow_root):
        return 0

    now = datetime.now(_KST)
    stale_count = 0

    for entry in os.listdir(workflow_root):
        entry_path = os.path.join(workflow_root, entry)
        if not os.path.isdir(entry_path) or entry.startswith("."):
            continue

        new_status = os.path.join(entry_path, "status.json")
        if os.path.exists(new_status):
            if _process_status_file(new_status, entry_path, now):
                stale_count += 1

    if stale_count > 0:
        print(f"[INFO] zombie cleanup: {stale_count} workflow(s) marked as STALE", file=sys.stderr)

    return stale_count


def _build_parser() -> argparse.ArgumentParser:
    """garbage_collect CLI argparse Creates and returns a parser."""
    parser = argparse.ArgumentParser(
        prog="flow-gc",
        description="Zombie Workflow Cleanup: TTL Expired + Incomplete status.json converted to STALE",
        epilog=build_common_epilog(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "project_root",
        nargs="?",
        default=None,
        metavar="project_root",
        help="Project root path (optional). Automatic detection based on script location if not specified",
    )
    return parser


def main() -> None:
    """CLI entry point. Receives project_root as an argument and organizes the zombie workflow."""
    parser = _build_parser()
    args = parser.parse_args()

    if args.project_root:
        project_root = args.project_root
    else:
        project_root = os.path.normpath(os.path.join(_SCRIPT_DIR, "..", "..", ".."))

    workflow_root = os.path.join(project_root, ".agent-factory", "runs")

    _log_dir = resolve_work_dir_for_logging(project_root)
    if _log_dir:
        append_log(_log_dir, "INFO", "garbage_collect: start")

    stale_count = _step1_mark_stale(workflow_root)

    if _log_dir and stale_count > 0:
        append_log(_log_dir, "INFO", f"garbage_collect: {stale_count} workflows marked STALE")

    if stale_count > 0:
        print("[STATE] GC", flush=True)
        print(f">> {stale_count} cleaned up", flush=True)
    else:
        print("[STATE] GC", flush=True)
        print(">>No change", flush=True)


if __name__ == "__main__":
    main()
