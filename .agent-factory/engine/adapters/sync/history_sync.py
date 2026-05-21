#!/usr/bin/env -S python3 -u
"""History synchronization and status check commands.

Scans the .agent-factory/runs/ and .agent-factory/runs/.history/ directories and compares them to .agent-factory/board/data/.history.md,
Add missing items or update status change items.

Directory structure:
    New structure: .agent-factory/runs/<YYYYMMDD-HHMMSS>/
                 status.json, plan.md, work/, report.md, .context.json
    Old structure (fallback): .agent-factory/runs/<YYYYMMDD-HHMMSS>/<workName>/<command>/

Main functions:
    parse_timestamp_from_dir: Extract date/time from directory name
    extract_status_from_json: Extract steps and timestamps from status.json
    is_stale: Determine whether the WORK/PLAN stage is stale
    scan_workflow_directory: Scan workflow directory
    cmd_sync: Execute sync subcommand
    cmd_status: Execute status subcommand
    cmd_archive: Execute archive subcommand

Usage:
    python3 .agent-factory/engine/sync/history_sync.py sync [--workflow-dir <path>] [--target <path>] [--dry-run] [--all]
    python3 .agent-factory/engine/sync/history_sync.py status [--workflow-dir <path>] [--target <path>] [--all]
    python3 .agent-factory/engine/sync/history_sync.py archive [registryKey]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import shutil
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Optional

_agent_factory_dir = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..")
)
if _agent_factory_dir not in sys.path:
    sys.path.insert(0, _agent_factory_dir)

try:
    from engine.common import (
        resolve_project_root,
    )
except ImportError:
    def resolve_project_root() -> str:
        return os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from engine.constants import STALE_TTL_SECONDS, KEEP_COUNT

# ============================================================
# Constant (Phase-state mapping)
# ============================================================

from engine.constants import HEADER_LINE, SEPARATOR_LINE, STEP_STATUS_MAP

TIMESTAMP_PATTERN = re.compile(r"^\d{8}-\d{6}$")
EXPECTED_CELL_COUNT = 12
ORPHAN_STATUS = "deleted"


# ============================================================
# helper function
# ============================================================

def _escape_pipe(text: str) -> str:
    """Escape pipe characters in Markdown table cells as HTML entities.

    Args:
        text: string to escape

    Returns:
        The pipe character (|) is &#String replaced with 124;
    """
    return text.replace("|", "&#124;")


def parse_timestamp_from_dir(dir_name: str) -> tuple[str, str]:
    """Extract date and time from YYYYMMDD-HHMMSS format.

    Args:
        dir_name: Directory name in the format YYYYMMDD-HHMMSS

    Returns:
        tuple: (formatted_date, formatted_time)
            - formatted_date: YYYY-MM-DD format
            - formatted_time: HH:MM format
    """
    date_part = dir_name[:8]
    time_part = dir_name[9:15]
    formatted_date = f"{date_part[:4]}-{date_part[4:6]}-{date_part[6:8]}"
    formatted_time = f"{time_part[:2]}:{time_part[2:4]}"
    return formatted_date, formatted_time


def extract_status_from_json(status_file: str) -> tuple[str, Optional[str], Optional[str]]:
    """Extract step(phase), created_at, and updated_at from status.json.

    Args:
        status_file: status.json file path

    Returns:
        tuple: (step, created_at, updated_at)
            - step: Current step string. “UNKNOWN” when parsing fails
            - created_at: ISO 8601 creation timestamp. None if not
            - updated_at: ISO 8601 update timestamp. None if not
    """
    try:
        with open(status_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        step = data.get("step") or data.get("phase", "UNKNOWN")
        created_at = data.get("created_at")
        updated_at = data.get("updated_at")
        return step, created_at, updated_at
    except (json.JSONDecodeError, IOError, KeyError):
        return "UNKNOWN", None, None


def is_stale(step: str, updated_at: Optional[str]) -> bool:
    """If more than 30 minutes have elapsed based on updated_at in the WORK or PLAN stage, it is judged to be stale.

    Args:
        step: Current workflow step (WORK, PLAN, INIT, REPORT, etc.)
        updated_at: Last update timestamp in ISO 8601 format. If None, returns False.

    Returns:
        Steil or not. STALE_TTL_SECONDS True if more than seconds have elapsed.
    """
    if step not in ("WORK", "PLAN", "INIT", "REPORT"):
        return False
    if not updated_at:
        return False
    try:
        # ISO 8601 format parsing (including time zone)
        updated_dt = datetime.fromisoformat(updated_at)
        now = datetime.now(updated_dt.tzinfo)
        elapsed = (now - updated_dt).total_seconds()
        return elapsed > STALE_TTL_SECONDS
    except (ValueError, TypeError):
        return False


def extract_summary_from_plan(plan_file: str, max_len: int = 60) -> str:
    """Extract the first sentence of the '## Task Summary' section from plan.md.

    Args:
        plan_file: plan.md file path
        max_len: Maximum number of characters to return. If it exceeds it, cut it off.

    Returns:
        Extracted summary string. Empty string if extraction fails.
    """
    try:
        with open(plan_file, "r", encoding="utf-8") as f:
            content = f.read()
        # Find the "## Task Summary" header
        match = re.search(r"##\s*Task\s*Summary\s* \n +(.+)", content)
        if match:
            summary = match.group(1).strip()
            if len(summary) > max_len:
                summary = summary[:max_len]
            return summary
    except (IOError, UnicodeDecodeError):
        pass
    return ""


def extract_summary_from_prompt(prompt_file: str, max_len: int = 60) -> str:
    """Extract the first line of user_prompt.txt as a summary.

    Args:
        prompt_file: user_prompt.txt file path
        max_len: Maximum number of characters to return. If it exceeds it, cut it off.

    Returns:
        Extracted first line string. Empty string if extraction fails.
    """
    try:
        with open(prompt_file, "r", encoding="utf-8") as f:
            first_line = f.readline().strip()
        if len(first_line) > max_len:
            first_line = first_line[:max_len]
        return first_line
    except (IOError, UnicodeDecodeError):
        return ""


def extract_summary_from_file(summary_file: str, max_len: int = 60) -> str:
    """Reads the first line of summary.txt, cuts it to within max_len, and returns it.

    Args:
        summary_file: summary.txt file path
        max_len: Maximum number of characters to return. If it exceeds it, cut it off.

    Returns:
        Extracted first line string. Empty string if the file is empty or a read failure occurs.
    """
    try:
        with open(summary_file, "r", encoding="utf-8") as f:
            first_line = f.readline().strip()
        if not first_line:
            return ""
        if len(first_line) > max_len:
            first_line = first_line[:max_len]
        return first_line
    except (IOError, UnicodeDecodeError):
        return ""


def extract_title_from_context(context_file: str) -> str:
    """Reads and returns the title field from .context.json. If JSON parsing fails, an empty string is returned.

    Args:
        context_file: .context.json file path

    Returns:
        title field value. Empty string if parsing fails or the title is missing.
    """
    try:
        with open(context_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        title = data.get("title", "")
        if isinstance(title, str) and title.strip():
            return title.strip()
    except (json.JSONDecodeError, IOError, KeyError):
        pass
    return ""


def ensure_entry_data(cmd_path: str) -> None:
    """Required files in a single workflow directory are verified and automatically created if missing.

    Target directory: <YYYYMMDD-HHMMSS>/<workName>/<command>/

    Files to be verified:
        - summary.txt: 1-line text summary file

    Auto-generated rules (summary.txt):
        Extract summary text with the following priorities and create summary.txt.
        (a) First sentence of the ‘## Task Summary’ section of plan.md
        (b) First line of user_prompt.txt
        (c) 'title' field in .context.json
        It is not created when extraction fails from any source.

    Args:
        cmd_path: <command> level directory absolute path
    """
    summary_file = os.path.join(cmd_path, "summary.txt")
    if os.path.exists(summary_file):
        return

    summary = ""

    # (a) First sentence of the ‘## Task Summary’ section of plan.md
    plan_file = os.path.join(cmd_path, "plan.md")
    if not summary and os.path.exists(plan_file):
        summary = extract_summary_from_plan(plan_file)

    # (b) First line of user_prompt.txt
    prompt_file = os.path.join(cmd_path, "user_prompt.txt")
    if not summary and os.path.exists(prompt_file):
        summary = extract_summary_from_prompt(prompt_file)

    # (c) 'title' field in .context.json
    context_file = os.path.join(cmd_path, ".context.json")
    if not summary and os.path.exists(context_file):
        try:
            with open(context_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            title = data.get("title", "")
            if isinstance(title, str) and title.strip():
                summary = title.strip()
                if len(summary) > 60:
                    summary = summary[:60]
        except (json.JSONDecodeError, IOError, KeyError):
            pass

    if summary:
        try:
            with open(summary_file, "w", encoding="utf-8") as f:
                f.write(summary + "\n")
        except IOError:
            pass


def _build_entry(
    dir_name: str,
    work_name: str,
    command: str,
    cmd_path: str,
    work_path: str,
    rel_prefix: str,
) -> dict[str, object]:
    """Internal helper that collects meta information of a single entry and returns it as a dict.

    Args:
        dir_name: Timestamped directory name in YYYYMMDD-HHMMSS format.
        work_name: Work name (workName subdirectory name)
        command: Command name (implement, review, etc.)
        cmd_path: <command> level directory absolute path
        work_path: <workName> level directory absolute path
        rel_prefix: Relative path prefix in history.md

    Returns:
        Entry meta information dictionary (work_id, title, summary, command, step, status,
        date, time, has_plan, has_prompt, has_files, files_count, has_report,
        (including has_work, work_name, rel_base)
    """
    ensure_entry_data(cmd_path)

    # Configure file path
    status_file = os.path.join(cmd_path, "status.json")
    plan_file = os.path.join(cmd_path, "plan.md")
    prompt_file = os.path.join(cmd_path, "user_prompt.txt")
    report_file = os.path.join(cmd_path, "report.md")
    files_dir = os.path.join(cmd_path, "files")

    # Extract meta information from status.json
    # Priority: <command>/status.json > <workName>/status.json
    step = "UNKNOWN"
    created_at = None
    updated_at = None
    if os.path.exists(status_file):
        step, created_at, updated_at = extract_status_from_json(status_file)
    else:
        # fallback: status.json at workName level
        work_status_file = os.path.join(work_path, "status.json")
        if os.path.exists(work_status_file):
            step, created_at, updated_at = extract_status_from_json(work_status_file)

    # T1: Stale detection - “interruption” when more than 2 hours elapse in the WORK/PLAN phase.
    if is_stale(step, updated_at):
        status_text = "interruption"
    else:
        status_text = STEP_STATUS_MAP.get(step, "unknown")

    # Date/Time Extraction
    date_str, time_str = parse_timestamp_from_dir(dir_name)

    # Extract summary (summary.txt first, plan.md second best, user_prompt.txt fallback)
    summary = ""
    summary_file = os.path.join(cmd_path, "summary.txt")
    if os.path.exists(summary_file):
        summary = extract_summary_from_file(summary_file)
    if not summary and os.path.exists(plan_file):
        summary = extract_summary_from_plan(plan_file)
    if not summary and os.path.exists(prompt_file):
        summary = extract_summary_from_prompt(prompt_file)

    # Title: title field in .context.json takes precedence, if not, fallback to work_name
    context_file = os.path.join(cmd_path, ".context.json")
    title = ""
    if os.path.exists(context_file):
        title = extract_title_from_context(context_file)
    if not title:
        title = work_name

    # Existence of each file/directory
    has_plan = os.path.exists(plan_file)
    has_prompt = os.path.exists(prompt_file)
    has_files = os.path.isdir(files_dir) and len(os.listdir(files_dir)) > 0
    has_report = os.path.exists(report_file)
    has_work = os.path.isdir(os.path.join(cmd_path, "work"))

    # Number of image files (files directory)
    files_count = 0
    if has_files:
        files_count = len(os.listdir(files_dir))

    return {
        "work_id": dir_name,
        "title": title,
        "summary": summary,
        "command": command,
        "step": step,
        "status": status_text,
        "date": date_str,
        "time": time_str,
        "has_plan": has_plan,
        "has_prompt": has_prompt,
        "has_files": has_files,
        "files_count": files_count,
        "has_report": has_report,
        "has_work": has_work,
        "work_name": work_name,
        "rel_base": f"{rel_prefix}/{dir_name}/{work_name}/{command}",
    }


def _scan_entries_in_dir(base_dir: str, rel_prefix: str) -> list[dict[str, object]]:
    """Scans a single directory and returns a list of workflow entries.

    After T-448, new fold structures are searched first, and old structures are treated as fallback.

    New structure (preferred): base_dir/<YYYYMMDD-HHMMSS>/status.json
        → Create 1 entry (work_name/command is read from .context.json)
    Phrase structure (fallback): base_dir/<YYYYMMDD-HHMMSS>/<workName>/<command>/
        If there is no command subdirectory and there is a file directly in workName, fallback to command="unknown".

    Args:
        base_dir: Absolute path to the base directory to scan
        rel_prefix: Relative path prefix in history.md
            (e.g. "../workflow" or "../workflow/.history")

    Returns:
        List of discovered workflow entries dictionary
    """
    entries: list[dict[str, object]] = []

    if not os.path.isdir(base_dir):
        return entries

    for dir_name in os.listdir(base_dir):
        dir_path = os.path.join(base_dir, dir_name)

        # Check for YYYYMMDD-HHMMSS pattern
        if not TIMESTAMP_PATTERN.match(dir_name):
            continue
        if not os.path.isdir(dir_path):
            continue

        new_status_file = os.path.join(dir_path, "status.json")
        if os.path.isfile(new_status_file):
            # New structure: extract work_name/command from .context.json
            context_file = os.path.join(dir_path, ".context.json")
            work_name = dir_name  # Fallback: use dir_name
            command = "unknown"
            if os.path.exists(context_file):
                try:
                    with open(context_file, "r", encoding="utf-8") as _f:
                        ctx = json.load(_f)
                    if isinstance(ctx.get("workName"), str) and ctx["workName"]:
                        work_name = ctx["workName"]
                    if isinstance(ctx.get("command"), str) and ctx["command"]:
                        command = ctx["command"]
                except Exception:
                    pass
            entry = _build_entry(dir_name, work_name, command,
                                 dir_path, dir_path, rel_prefix)
            # New structure: rel_base is {rel_prefix}/{dir_name} (no intermediate directories)
            entry["rel_base"] = f"{rel_prefix}/{dir_name}"
            entries.append(entry)
            continue

        # Sphere structure fallback: Nested structure navigation <YYYYMMDD-HHMMSS>/<workName>/<command>/
        for work_name in os.listdir(dir_path):
            work_path = os.path.join(dir_path, work_name)
            if not os.path.isdir(work_path):
                continue

            # command subdirectory navigation
            has_command_subdir = False
            for command in os.listdir(work_path):
                cmd_path = os.path.join(work_path, command)
                if not os.path.isdir(cmd_path):
                    continue

                has_command_subdir = True
                entry = _build_entry(dir_name, work_name, command,
                                     cmd_path, work_path, rel_prefix)
                entries.append(entry)

            # T2: Fallback if there is no command directory and a file exists directly in workName.
            if not has_command_subdir:
                work_status = os.path.join(work_path, "status.json")
                work_prompt = os.path.join(work_path, "user_prompt.txt")
                if os.path.exists(work_status) or os.path.exists(work_prompt):
                    entry = _build_entry(dir_name, work_name, "unknown",
                                         work_path, work_path, rel_prefix)
                    entries.append(entry)

    return entries


def scan_workflow_directory(workflow_dir: str, include_all: bool = False) -> list[dict[str, object]]:
    """Scans the .agent-factory/runs/ and .agent-factory/runs/.history/ directories to extract metainformation for each job.

    Directory structure:
        New structure: .agent-factory/runs/<YYYYMMDD-HHMMSS>/status.json
        Old structure (fallback): .agent-factory/runs/<YYYYMMDD-HHMMSS>/<workName>/<command>/
    The .history/ sub is also searched with the same structure, and the rel_base is composed of ../workflow/.history/....

    workflow/ entries take precedence over .history/ entries (if they have the same work_id).

    Args:
        workflow_dir: Absolute path to the .agent-factory/runs/ directory.
        include_all: If True, also includes interrupted tasks. Currently unused.

    Returns:
        Dictionary list of discovered workflow entries (sorted by reverse date)
    """
    # Scan .agent-factory/runs/ (priority)
    entries = _scan_entries_in_dir(workflow_dir, "../workflow")

    # Already collected work_id set (priority protected)
    seen_ids = {e["work_id"] for e in entries}

    # Scan .agent-factory/runs/.history/
    history_dir = os.path.join(workflow_dir, ".history")
    history_entries = _scan_entries_in_dir(history_dir, "../workflow/.history")

    # Add only items not in workflow/
    for entry in history_entries:
        if entry["work_id"] not in seen_ids:
            entries.append(entry)
            seen_ids.add(entry["work_id"])

    # Sort by reverse date (newest)
    entries.sort(key=lambda x: x["work_id"], reverse=True)
    return entries


def format_row(entry: dict[str, object]) -> str:
    """Create a 10-column table row.

    Args:
        entry: Workflow entry dictionary returned by _build_entry()

    Returns:
        Markdown table row string (with | separator)
    """
    # Date cell: YYYY-MM-DD<br><sub>HH:MM</sub>
    date_cell = f"{entry['date']}<br><sub>{entry['time']}</sub>"

    # Title & Content Cell: Title<br><sub>Summary</sub>
    if entry["summary"]:
        title_cell = f"{_escape_pipe(str(entry['title']))}<br><sub>{_escape_pipe(str(entry['summary']))}</sub>"
    else:
        title_cell = _escape_pipe(str(entry["title"]))

    # query link
    if entry["has_prompt"]:
        prompt_cell = f"[Query]({entry['rel_base']}/user_prompt.txt)"
    else:
        prompt_cell = "-"

    # file link
    if entry["has_files"]:
        files_cell = f"[file({entry['files_count']})]({entry['rel_base']}/files/)"
    else:
        files_cell = "-"

    # plan link
    if entry["has_plan"]:
        plan_cell = f"[plan]({entry['rel_base']}/plan.md)"
    else:
        plan_cell = "-"

    # work link
    if entry["has_work"]:
        work_cell = f"[work]({entry['rel_base']}/work/)"
    else:
        work_cell = "-"

    # reporting link
    if entry["has_report"]:
        report_cell = f"[report]({entry['rel_base']}/report.md)"
    else:
        report_cell = "-"

    return f"| {date_cell} | {entry['work_id']} | {title_cell} | {entry['command']} | {entry['status']} | {prompt_cell} | {files_cell} | {plan_cell} | {work_cell} | {report_cell} |"


# ============================================================
# Parsing history.md
# ============================================================

def parse_history_md(filepath: str) -> tuple[list[str], set[str], int, list[str]]:
    """Parses history.md and returns its components.

    Args:
        filepath: history.md file path. If the file does not exist, an empty result is returned.

    Returns:
        tuple: (header_lines, existing_ids, marker_idx, data_rows)
            - header_lines: Header part up to the marker (including marker)
            - existing_ids: Set existing task ID
            - marker_idx: Index of marker line (none if -1)
            - data_rows: list of data rows (excluding table header/separator lines)
    """
    if not os.path.exists(filepath):
        return [], set(), -1, []

    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    header_lines: list[str] = []
    data_rows: list[str] = []
    existing_ids: set[str] = set()
    marker_idx = -1
    in_table = False
    table_header_seen = False
    header_separator_seen = False

    for i, line in enumerate(lines):
        stripped = line.rstrip("\n")

        # Table header/separator line detection
        if "| date" in stripped and "Job ID" in stripped:
            in_table = True
            table_header_seen = True
            header_lines.append(line)
            continue

        if table_header_seen and stripped.startswith("|---"):
            if not header_separator_seen:
                # First separator line immediately after the table header -> part of the header
                header_lines.append(line)
                header_separator_seen = True
            # Ignore middle separators between data rows (do not add them to data_rows)
            continue

        # data row
        if in_table and stripped.startswith("|"):
            data_rows.append(stripped)
            # Extract task ID (2nd cell)
            cells = stripped.split("|")
            if len(cells) >= 3:
                work_id = cells[2].strip()
                if TIMESTAMP_PATTERN.match(work_id):
                    existing_ids.add(work_id)
        elif not in_table:
            header_lines.append(line)

    return header_lines, existing_ids, marker_idx, data_rows


def extract_status_from_row(row: str) -> str:
    """Extract status cell values ​​from existing data rows.

    Args:
        row: Markdown table data row string

    Returns:
        Status cell value string. An empty string if there are not enough cells.
    """
    cells = row.split("|")
    if len(cells) >= 6:
        return cells[5].strip()
    return ""


def replace_status_in_row(row: str, new_status: str) -> str:
    """Replace the status cell value in an existing data row.

    Args:
        row: Markdown table data row string
        new_status: New status value to replace

    Returns:
        The row string in which the status cell was replaced. If there are not enough cells, return the original row.
    """
    cells = row.split("|")
    if len(cells) >= 6:
        cells[5] = f" {new_status} "
        return "|".join(cells)
    return row


def extract_work_id_from_row(row: str) -> str:
    """Extract job ID from existing data row.

    Args:
        row: Markdown table data row string

    Returns:
        Job ID string. An empty string if there are not enough cells.
    """
    cells = row.split("|")
    if len(cells) >= 3:
        return cells[2].strip()
    return ""


# ============================================================
# sync command
# ============================================================

def cmd_sync(args: argparse.Namespace) -> int:
    """Execute sync subcommand.

    Scans the .agent-factory/runs/ directory and compares it to history.md and synchronizes missing/changed entries.

    Args:
        args: argparse. Namespace. Includes workflow_dir, target, dry_run, all properties.

    Returns:
        Exit code. 0: success, 1: failure
    """
    print("[STATE] HISTORY sync", flush=True)
    print(">> Start sync...", flush=True)

    workflow_dir = args.workflow_dir
    target = args.target
    dry_run = args.dry_run
    include_all = args.all

    # Convert relative path to absolute path based on PROJECT_ROOT
    if not os.path.isabs(target):
        target = os.path.join(PROJECT_ROOT, target)
    if not os.path.isabs(workflow_dir):
        workflow_dir = os.path.join(PROJECT_ROOT, workflow_dir)

    # Scan .agent-factory/runs/
    scanned = scan_workflow_directory(workflow_dir, include_all)
    if not scanned:
        print("[INFO] There are no tasks in the .agent-factory/runs/ directory.")
        return 0

    # Parsing history.md
    header_lines, existing_ids, marker_idx, data_rows = parse_history_md(target)

    # Organize scanned data into work_id -> entry map
    # (workflow/ is already prioritized in scan_workflow_directory)
    scanned_map: dict[str, dict[str, object]] = {}
    for entry in scanned:
        scanned_map.setdefault(entry["work_id"], entry)

    # Convert existing rows to work_id -> row dictionary
    # Original rows are also preserved for legacy format detection
    existing_rows: dict[str, str] = {}
    original_rows: dict[str, str] = {}
    for row in data_rows:
        wid = extract_work_id_from_row(row)
        if wid:
            if wid in scanned_map:
                existing_rows[wid] = format_row(scanned_map[wid])
            else:
                existing_rows[wid] = row
            original_rows.setdefault(wid, row)

    # Comparison: Detecting missing items and state change/legacy format items
    new_entries: list[dict[str, object]] = []
    updated_entries: list[dict[str, object]] = []

    for entry in scanned:
        wid = entry["work_id"]
        if wid not in existing_ids:
            new_entries.append(entry)
        else:
            # Check status change
            old_row = original_rows.get(wid, "")
            old_status = extract_status_from_row(old_row)
            new_status = entry["status"]
            if old_status != new_status:
                updated_entries.append(entry)
            else:
                # Detect legacy format rows (less than 9 columns): O(1) dict lookup
                orig_row = original_rows.get(wid, "")
                if orig_row and len(orig_row.split("|")) < EXPECTED_CELL_COUNT:
                    updated_entries.append(entry)

    # Check for existence of duplicate rows
    wid_counts: dict[str, int] = {}
    for row in data_rows:
        wid = extract_work_id_from_row(row)
        if wid:
            wid_counts[wid] = wid_counts.get(wid, 0) + 1
    has_duplicates = any(c > 1 for c in wid_counts.values())

    # Check for legacy format row existence (cell count less than 10)
    has_legacy = any(
        len(row.split("|")) < EXPECTED_CELL_COUNT
        for row in data_rows
        if extract_work_id_from_row(row)
    )

    # T3: Orphan entry detection - entries in history.md but no directory in filesystem
    orphan_wids: set[str] = set()
    for row in data_rows:
        wid = extract_work_id_from_row(row)
        if wid and wid not in scanned_map:
            old_status = extract_status_from_row(row)
            if old_status != ORPHAN_STATUS:
                orphan_wids.add(wid)

    if not new_entries and not updated_entries and not has_duplicates and not has_legacy and not orphan_wids:
        print("[INFO] history.md is up to date. No changes.")
        return 0

    # dry-run mode
    if dry_run:
        print("[DRY-RUN] Scheduled changes:")
        print(f"New addition: {len(new_entries)} entries")
        for e in new_entries:
            print(f"    + {e['work_id']} | {e['title']} | {e['command']} | {e['status']}")
        print(f"Status update: {len(updated_entries)} entries")
        for e in updated_entries:
            old_row = original_rows.get(str(e["work_id"]), "")
            old_status = extract_status_from_row(old_row)
            print(f"    ~ {e['work_id']} | {old_status} -> {e['status']}")
        if orphan_wids:
            print(f"Orphan entries (marked deleted): {len(orphan_wids)} occurrences")
            for wid in sorted(orphan_wids, reverse=True):
                print(f"! {wid} | deleted")
        return 0

    # actual renewal
    # 1. Apply a state change on an existing row
    updated_row_map: dict[str, str] = {}
    for entry in updated_entries:
        updated_row_map[str(entry["work_id"])] = format_row(entry)

    # 2. Reorganize entire data (update existing rows + add new rows)
    final_rows: list[str] = []

    # Create new row
    new_rows = [format_row(e) for e in new_entries]

    # Update existing row (regenerate with format_row if scanned data exists)
    for row in data_rows:
        wid = extract_work_id_from_row(row)
        if wid in updated_row_map:
            final_rows.append(updated_row_map[wid])
        elif wid in scanned_map:
            # Regeneration with scanned data (resolving legacy formats/missing links)
            final_rows.append(format_row(scanned_map[wid]))
        elif wid in orphan_wids:
            # T3: Orphan entry - change status to "deleted"
            final_rows.append(replace_status_in_row(row, ORPHAN_STATUS))
        else:
            final_rows.append(row)

    # Insert new rows by date (merge and reorder everything)
    # Filter out middle separator rows so they are not included in the final output
    all_rows = [r for r in (final_rows + new_rows) if not r.strip().startswith("|---")]

    # Sort by task ID (reverse order)
    def sort_key(row: str) -> str:
        """Returns the task ID of the row as the sort key."""
        wid = extract_work_id_from_row(row)
        return wid if wid else ""

    all_rows.sort(key=sort_key, reverse=True)

    # Remove duplicate rows by work_id (keep only first row after sorting)
    seen_wids: set[str] = set()
    deduped_rows: list[str] = []
    for row in all_rows:
        wid = extract_work_id_from_row(row)
        if wid and wid in seen_wids:
            continue
        if wid:
            seen_wids.add(wid)
        deduped_rows.append(row)
    all_rows = deduped_rows

    # Reorganize the history.md file
    output_lines: list[str] = []

    # title
    output_lines.append("# Workflow execution history \n")
    output_lines.append("\n")
    output_lines.append(f"{HEADER_LINE}\n")
    output_lines.append(f"{SEPARATOR_LINE}\n")

    for row in all_rows:
        output_lines.append(f"{row}\n")

    # Atomic Write
    target_dir = os.path.dirname(target)
    os.makedirs(target_dir, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(dir=target_dir, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.writelines(output_lines)
        shutil.move(tmp_path, target)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise

    # Summary of Results
    print(f"[SYNC] Done:")
    print(f"New addition: {len(new_entries)} entries")
    for e in new_entries:
        print(f"    + {e['work_id']} | {e['title']} | {e['command']} | {e['status']}")
    if updated_entries:
        print(f"Status update: {len(updated_entries)} entries")
        for e in updated_entries:
            old_row = original_rows.get(str(e["work_id"]), "")
            old_status = extract_status_from_row(old_row)
            print(f"    ~ {e['work_id']} | {old_status} -> {e['status']}")
    if orphan_wids:
        print(f"Orphan entries (marked deleted): {len(orphan_wids)} occurrences")
        for wid in sorted(orphan_wids, reverse=True):
            print(f"! {wid} | deleted")
    print(f"Total number of rows: {len(all_rows)}")

    print(">> [OK] sync completed", flush=True)
    return 0


# ============================================================
# status command
# ============================================================

def cmd_status(args: argparse.Namespace) -> int:
    """Execute status subcommand.

    Compares the .agent-factory/runs/ directory with history.md and outputs a synchronization status summary.

    Args:
        args: argparse. Namespace. Includes workflow_dir, target, and all properties.

    Returns:
        Exit code. Always 0.
    """
    workflow_dir = args.workflow_dir
    target = args.target
    include_all = args.all

    # Convert relative path to absolute path based on PROJECT_ROOT
    if not os.path.isabs(target):
        target = os.path.join(PROJECT_ROOT, target)
    if not os.path.isabs(workflow_dir):
        workflow_dir = os.path.join(PROJECT_ROOT, workflow_dir)

    # Scan .agent-factory/runs/
    scanned = scan_workflow_directory(workflow_dir, include_all)

    # Parsing history.md
    _, existing_ids, _, data_rows = parse_history_md(target)

    # Count missing items
    scanned_ids = {e["work_id"] for e in scanned}
    missing_ids = scanned_ids - existing_ids
    extra_ids = existing_ids - scanned_ids

    # Classification by status
    status_counts: dict[str, int] = {}
    for entry in scanned:
        s = str(entry["status"])
        status_counts[s] = status_counts.get(s, 0) + 1

    # output of power
    print("[STATE] HISTORY status", flush=True)
    print(f">> workflow: {len(scanned)} rows, history: {len(data_rows)} rows, missing: {len(missing_ids)} rows", flush=True)
    print("=== history-sync status ===")
    print(f"Number of workflow/ directories: {len(scanned)}")
    print(f"history.md row count: {len(data_rows)} rows")
    print(f"Missing items: {len(missing_ids)}")
    if extra_ids:
        print(f"Exists only in history.md: {len(extra_ids)} items")
    print()
    print("Classification by status:")
    for status, count in sorted(status_counts.items(), key=lambda x: -x[1]):
        print(f"{status}: {count} cases")

    if missing_ids:
        print()
        print("List of missing items:")
        for entry in scanned:
            if entry["work_id"] in missing_ids:
                print(f"    - {entry['work_id']} | {entry['title']} | {entry['command']} | {entry['status']}")

    return 0


# ============================================================
# archive command
# ============================================================

def _update_ticket_workdir_after_archive(moved_key: str, workflow_dir: str, history_dir: str) -> None:
    """After archiving, update the path field in the ticket XML holding the moved registryKey to the .history/ reflection path.

    Tickets Scan the entire directory (open/progress/review/done) to see if <result>/<registrykey> is
    Find the ticket XML matching moved_key, and replace the <workdir>/<plan>/<report> path text with
    Update in .agent-factory/runs/.history/{key}/... format.

    Args:
        moved_key: Workflow key moved to .history/ (format YYYYMMDD-HHMMSS)
        workflow_dir: Absolute path to the .agent-factory/runs/ directory.
        history_dir: Absolute path to the .agent-factory/runs/.history/ directory.

    Returns:
        None. In case of failure, a [WARN] warning is output and non-blocking processing is performed.
    """
    # workflow_dir = .../PROJECT/.agent-factory/workflow
    # workflow_dir parent = .../PROJECT/.agent-factory
    cw_dir = os.path.dirname(workflow_dir)
    tickets_dir = os.path.join(cw_dir, "tickets")

    status_dirs = ["open", "progress", "review", "done"]

    # Path update function: .agent-factory/runs/{key}/... -> .agent-factory/runs/.history/{key}/...
    def _rewrite_path(text: str) -> str:
        """Change workflow/{key}/ to workflow/.history/{key}/に置換."""
        if not text:
            return text
        old_prefix = f".agent-factory/runs/{moved_key}/"
        new_prefix = f".agent-factory/runs/.history/{moved_key}/"
        if old_prefix in text:
            return text.replace(old_prefix, new_prefix)
        return text

    for status in status_dirs:
        status_dir = os.path.join(tickets_dir, status)
        if not os.path.isdir(status_dir):
            continue
        for fname in os.listdir(status_dir):
            if not fname.endswith(".xml"):
                continue
            xml_path = os.path.join(status_dir, fname)
            ticket_number = fname[:-4]  # T-NNN
            try:
                tree = ET.parse(xml_path)
                root = tree.getroot()
                result_el = root.find("result")
                if result_el is None:
                    continue
                rk_el = result_el.find("registrykey")
                if rk_el is None or (rk_el.text or "").strip() != moved_key:
                    continue

                # registrykey match — update path workdir/plan/report
                updated = False
                for tag in ("workdir", "plan", "report"):
                    el = result_el.find(tag)
                    if el is not None and el.text:
                        new_text = _rewrite_path(el.text.strip())
                        if new_text != el.text.strip():
                            el.text = new_text
                            updated = True

                if updated:
                    tree.write(xml_path, encoding="unicode", xml_declaration=False)
                    new_workdir = (result_el.find("workdir") or result_el).text or ""
                    print(
                        f"[OK] ticket {ticket_number}: workdir updated to .history/"
                    )
            except Exception as exc:
                print(
                    f"[WARN] ticket {ticket_number}: XML workdir update failed — {exc}",
                    file=sys.stderr,
                )


def _detect_active_workflow_keys(workflow_dir: str) -> set[str]:
    """Returns a set of directory names for active workflows (not completed).

    After T-448, new fold structures are searched first, and old structures are treated as fallback.
    New structure: dir_path/status.json direct
    Old structure fallback: dir_path/<workName>/<command>/status.json

    Args:
        workflow_dir: Absolute path to the .agent-factory/runs/ directory.

    Returns:
        Set of incomplete (non-DONE/FAILED/CANCELLED) workflow directory names
    """
    active_keys: set[str] = set()
    terminal_phases = {"DONE", "FAILED", "CANCELLED"}

    if not os.path.isdir(workflow_dir):
        return active_keys

    for dir_name in os.listdir(workflow_dir):
        dir_path = os.path.join(workflow_dir, dir_name)
        if not os.path.isdir(dir_path) or not re.match(r"^[0-9]", dir_name):
            continue

        # New fold structure priority: check dir_path/status.json directly
        new_status_file = os.path.join(dir_path, "status.json")
        if os.path.exists(new_status_file):
            phase, _, _ = extract_status_from_json(new_status_file)
            if phase not in terminal_phases:
                active_keys.add(dir_name)
            continue

        # Phrase structure fallback: workName subdirectory navigation
        for work_name in os.listdir(dir_path):
            work_path = os.path.join(dir_path, work_name)
            if not os.path.isdir(work_path):
                continue

            # command subdirectory navigation
            for command in os.listdir(work_path):
                cmd_path = os.path.join(work_path, command)
                if not os.path.isdir(cmd_path):
                    continue
                status_file = os.path.join(cmd_path, "status.json")
                if os.path.exists(status_file):
                    phase, _, _ = extract_status_from_json(status_file)
                    if phase not in terminal_phases:
                        active_keys.add(dir_name)
                        break
            else:
                continue
            break

    return active_keys


def cmd_archive(args: argparse.Namespace) -> int:
    """Execute the archive subcommand. Move old workflow directories to .history/.

    Move older directories exceeding KEEP_COUNT to .agent-factory/runs/.history/.
    If registry_key is specified, the key is preserved; if not, active workflows are automatically detected and excluded.

    Args:
        args: argparse. Namespace. Includes registry_key attribute (can be None).

    Returns:
        Exit code. 0: success, 1: partial failure
    """
    print("[STATE] HISTORY archive", flush=True)
    current_key = getattr(args, 'registry_key', None)
    workflow_dir = os.path.join(PROJECT_ROOT, ".agent-factory", "runs")
    history_dir = os.path.join(workflow_dir, ".history")

    if not os.path.isdir(workflow_dir):
        print(">> No workflow directory — skipped", flush=True)
        return 0

    # [0-9]* Sort pattern directory in reverse order.
    dirs: list[str] = []
    for name in sorted(os.listdir(workflow_dir), reverse=True):
        full_path = os.path.join(workflow_dir, name)
        if os.path.isdir(full_path) and re.match(r"^[0-9]", name):
            dirs.append(name)

    if not dirs:
        print(">>No archive destination", flush=True)
        return 0

    # If registry_key is None, active workflows are automatically detected and excluded.
    if current_key:
        filtered = [d for d in dirs if d != current_key]
        if len(filtered) < KEEP_COUNT - 1:
            print(">> Less than retention quantity — skipped", flush=True)
            return 0

        # Create .history/ directory
        os.makedirs(history_dir, exist_ok=True)

        moved = 0
        failed = 0
        for target in filtered[KEEP_COUNT - 1:]:
            src = os.path.join(workflow_dir, target)
            dst = os.path.join(history_dir, target)
            try:
                shutil.move(src, dst)
                moved += 1
                print(f"[OK] archived: {target}")
                _update_ticket_workdir_after_archive(target, workflow_dir, history_dir)
            except Exception:
                failed += 1
                print(f"[WARN] archive failed: {target} (skipping)", file=sys.stderr)
    else:
        active_keys = _detect_active_workflow_keys(workflow_dir)
        filtered = [d for d in dirs if d not in active_keys]
        keep = max(0, KEEP_COUNT - len(active_keys))
        if len(filtered) < keep:
            print(">> Less than retention quantity — skipped", flush=True)
            return 0

        # Create .history/ directory
        os.makedirs(history_dir, exist_ok=True)

        moved = 0
        failed = 0
        for target in filtered[keep:]:
            src = os.path.join(workflow_dir, target)
            dst = os.path.join(history_dir, target)
            try:
                shutil.move(src, dst)
                moved += 1
                print(f"[OK] archived: {target}")
                _update_ticket_workdir_after_archive(target, workflow_dir, history_dir)
            except Exception:
                failed += 1
                print(f"[WARN] archive failed: {target} (skipping)", file=sys.stderr)

    if moved > 0:
        print(f">> {moved} directories archived", flush=True)
    else:
        print(">>No change", flush=True)

    if failed > 0:
        print(f"[WARN] {failed} directories failed to archive", file=sys.stderr)
        return 1

    return 0


# ============================================================
# main
# ============================================================

PROJECT_ROOT = resolve_project_root()


def main() -> int:
    """CLI entry point. Parse and execute subcommands (sync/status/archive).

    Returns:
        Exit code. 0: success, 1: failure
    """
    parser = argparse.ArgumentParser(description="history sync/status core")
    subparsers = parser.add_subparsers(dest="subcmd", required=True)

    # sync subcommand
    sync_parser = subparsers.add_parser("sync", help="sync history.md")
    sync_parser.add_argument("--workflow-dir", default=os.path.join(PROJECT_ROOT, ".agent-factory", "runs"), help=".workflow directory path")
    sync_parser.add_argument("--target", default=os.path.join(PROJECT_ROOT, ".agent-factory", "board", "data", ".history.md"), help=".history.md file path")
    sync_parser.add_argument("--dry-run", action="store_true", help="Only preview changes")
    sync_parser.add_argument("--all", action="store_true", help="Includes interrupt operations")

    # status subcommand
    status_parser = subparsers.add_parser("status", help="Sync status summary")
    status_parser.add_argument("--workflow-dir", default=os.path.join(PROJECT_ROOT, ".agent-factory", "runs"), help=".workflow directory path")
    status_parser.add_argument("--target", default=os.path.join(PROJECT_ROOT, ".agent-factory", "board", "data", ".history.md"), help=".history.md file path")
    status_parser.add_argument("--all", action="store_true", help="Includes interrupt operations")

    # archive subcommand
    archive_parser = subparsers.add_parser("archive", help="Archive old workflows to .history/")
    archive_parser.add_argument("registry_key", nargs='?', default=None, help="registryKey of the current workflow (if omitted, active workflow will be automatically detected)")

    args = parser.parse_args()

    if args.subcmd == "sync":
        try:
            return cmd_sync(args)
        except Exception as e:
            print(f"[FAIL] sync failed: {e}", file=sys.stderr)
            return 1
    elif args.subcmd == "status":
        return cmd_status(args)
    elif args.subcmd == "archive":
        try:
            return cmd_archive(args)
        except Exception as e:
            print(f"[FAIL] archive failed: {e}", file=sys.stderr)
            return 1
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
