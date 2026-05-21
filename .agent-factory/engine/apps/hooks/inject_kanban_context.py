"""inject_kanban_context.py — UserPromptSubmit hook: Kanban/session snapshot context builder.

Input: stdin JSON (UserPromptSubmit payload, content can be ignored)
Output: stdout JSON
  {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": "<text>"}}

use:
  The main session automatically recognizes the Kanban board status + active workflow session every user turn.
  Injected as additionalContext. Because the W03 dispatcher skips the call in a workflow session,
  This module does not contain main session identification logic.

Output Limit:
  - When the payload exceeds 4096 chars, only the top 10 are displayed in Open/In Progress details.
  - 0.8s soft deadline: When exceeded, partial payload is output and terminated.

Failure Policy:
  - Guaranteed exit 0 + empty stdout in any exception (no blocking of user turn)
"""

from __future__ import annotations

import glob
import json
import os
import signal
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from typing import Any

# ── Constant ────────────────────────────────────────────────────────────────────────

MAX_PAYLOAD_CHARS = 4096
MAX_DETAIL_ITEMS = 10
SESSIONS_TIMEOUT = 0.7   # flow-sessions subprocess timeout (seconds)
SOFT_DEADLINE = 0.8      # Total soft deadline (seconds)

# Column directory name → display label
COLUMN_LABELS: dict[str, str] = {
    "open": "Open",
    "progress": "In Progress",
    "review": "Review",
    "todo": "To Do",
    "done": "Done",
}

# ── Project root navigation ───────────────────────────────────────────────────────────

def _find_project_root() -> str:
    """Same logic as dispatcher.py: Browse main repo root with git-common-dir."""
    d = os.path.dirname(os.path.abspath(__file__))
    # .agent-factory/engine/apps/hooks/ → project root = ../../../..
    root = os.path.normpath(os.path.join(d, '..', '..', '..', '..'))

    # If it is the main repo, it is returned as is (check the existence of .settings)
    if os.path.exists(os.path.join(root, '.agent-factory', '.settings')):
        return root

    # Could be a worktree — navigate the main repo with git-common-dir
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--path-format=absolute', '--git-common-dir'],
            capture_output=True, text=True, timeout=5, cwd=root,
        )
        if result.returncode == 0:
            git_common = result.stdout.strip()
            main_root = os.path.dirname(git_common)
            main_cw_dir = os.path.join(main_root, '.agent-factory')
            if os.path.exists(os.path.join(main_cw_dir, '.settings')):
                return main_root
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    return root


# ── Collect Kanban Summary ────────────────────────────────────────────────────────────────

def _parse_ticket_header(xml_path: str) -> dict[str, str] | None:
    """Quickly extracts only metadata fields from XML files.

    Early stopping after parsing metadata sections using ET.iterparse.
    Input/Output:
        xml_path: Absolute path to T-NNN.xml
        return: {"number": "T-NNN", "title": "...", "status": "..."} or None
    """
    try:
        fields: dict[str, str] = {}
        target_tags = {"number", "title", "status"}
        context = ET.iterparse(xml_path, events=("end",))
        for _event, elem in context:
            tag = elem.tag
            if tag in target_tags:
                text = (elem.text or "").strip()
                if text:
                    fields[tag] = text
                # Stop early when all three fields are collected.
                if len(fields) >= 3:
                    break
            # Not needed after metadata closing tag — stop early
            if tag == "metadata" and len(fields) >= 1:
                break
        if "number" not in fields:
            return None
        return fields
    except Exception:
        return None


def _collect_kanban_summary(project_root: str) -> dict[str, Any]:
    """Collect ticket summaries by Kanban column.

    The open/progress/review column extracts ID + title + status.
    The todo/done column returns only counts (saving payload size).

    Input: project_root — Main repo root path
    output: {
        "counts": {"open": N, "progress": M, "review": K, "todo": A, "done": B},
        "details": [{"number": "T-NNN", "title": "...", "status": "...", "column": "open"}, ...]
    }
    """
    tickets_dir = os.path.join(project_root, '.agent-factory', 'tickets')
    counts: dict[str, int] = {}
    details: list[dict[str, str]] = []

    for col in ("open", "progress", "review", "todo", "done"):
        col_dir = os.path.join(tickets_dir, col)
        if not os.path.isdir(col_dir):
            counts[col] = 0
            continue

        xml_files = glob.glob(os.path.join(col_dir, "T-*.xml"))
        counts[col] = len(xml_files)

        # todo/done is just a count (no details needed)
        if col in ("todo", "done"):
            continue

        for xml_path in sorted(xml_files):
            header = _parse_ticket_header(xml_path)
            if header:
                details.append({
                    "number": header.get("number", ""),
                    "title": header.get("title", ""),
                    "status": header.get("status", ""),
                    "column": col,
                })

    return {"counts": counts, "details": details}


# ── Collect active sessions ────────────────────────────────────────────────────────────────

def _parse_sessions_json(raw: str) -> list[dict[str, str]]:
    """flow-sessions --Normalize json output to a dict list.

    flow-sessions --json returns a session array JSON or an empty array.
    Output format: [{"ticket": "T-NNN", "command": "implement", "started_at": "HHMMSS", "status": "running"}, ...]
    """
    try:
        data = json.loads(raw)
        if not isinstance(data, list):
            return []
        sessions: list[dict[str, str]] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            sessions.append({
                "ticket": str(item.get("ticket_id") or item.get("ticket") or ""),
                "command": str(item.get("command") or ""),
                "started_at": str(item.get("started_at") or item.get("start_time") or ""),
                "status": str(item.get("status") or "running"),
                "registry_key": str(item.get("registry_key") or ""),
            })
        return sessions
    except Exception:
        return []


def _fallback_sessions(project_root: str) -> list[dict[str, str]]:
    """.agent-factory/runs/ sub context.json mtime stat fallback.

    Board server does not start + directly scans the runs/ directory when flow-sessions fail.
    Returns only the top 5 by most recent mtime.
    """
    runs_dir = os.path.join(project_root, '.agent-factory', 'runs')
    if not os.path.isdir(runs_dir):
        return []

    sessions: list[dict[str, str]] = []
    # New structure: runs/{registryKey}/.context.json (fold)
    pattern_new = os.path.join(runs_dir, '*', '.context.json')
    # Spherical structure fallback: runs/{registryKey}/{slug}/implement/.context.json
    pattern_old = os.path.join(runs_dir, '*', '*', 'implement', '.context.json')
    ctx_files = glob.glob(pattern_new) + glob.glob(pattern_old)

    for ctx_path in ctx_files:
        try:
            mtime = os.path.getmtime(ctx_path)
            with open(ctx_path, 'r', encoding='utf-8') as f:
                ctx = json.load(f)
            if not isinstance(ctx, dict):
                continue
            ticket = str(ctx.get("ticket_id") or ctx.get("ticketNumber") or "")
            command = str(ctx.get("command") or "")
            registry_key = str(ctx.get("registry_key") or ctx.get("registryKey") or "")
            started_at = ""
            if registry_key and len(registry_key) >= 15:
                # registryKey = YYYYMMDD-HHMMSS → extract HHMMSS
                started_at = registry_key[9:15] if "-" in registry_key else registry_key[-6:]
            sessions.append({
                "ticket": ticket,
                "command": command,
                "started_at": started_at,
                "status": "running",
                "registry_key": registry_key,
                "_mtime": mtime,  # For sorting
            })
        except Exception:
            continue

    # mtime Sort in descending order, then only the top 5
    sessions.sort(key=lambda x: float(x.get("_mtime", 0)), reverse=True)
    for s in sessions:
        s.pop("_mtime", None)

    return sessions[:5]


def _collect_active_sessions(project_root: str) -> list[dict[str, str]]:
    """Collect a list of active workflow sessions.

    1st: call flow-sessions --json subprocess (timeout=0.7s)
    Secondary fallback: .agent-factory/runs/ direct stat

    Output: [{"ticket": "T-NNN", "command": "implement", "started_at": "HHMMSS", "status": "running"}, ...]
    """
    bin_dir = os.path.join(project_root, '.agent-factory', 'bin')
    flow_sessions = os.path.join(bin_dir, 'flow-sessions')

    if os.path.isfile(flow_sessions):
        try:
            result = subprocess.run(
                [flow_sessions, '--json'],
                capture_output=True,
                text=True,
                timeout=SESSIONS_TIMEOUT,
                cwd=project_root,
            )
            if result.returncode == 0 and result.stdout.strip():
                parsed = _parse_sessions_json(result.stdout)
                if parsed is not None:  # An empty list is also a valid result
                    return parsed
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError, Exception):
            pass

    # fallback: runs/ direct scan
    return _fallback_sessions(project_root)


# ── Context Formatting ────────────────────────────────────────────────────────────────

def _format_hhmm(started_at: str) -> str:
    """Extract HH:MM from HHMMSS or YYYYMMDD-HHMMSS format."""
    s = started_at.strip()
    if not s:
        return ""
    # ISO datetime format handling
    if "T" in s or " " in s:
        parts = s.replace("T", " ").split(" ")
        if len(parts) >= 2:
            time_part = parts[1][:5]  # HH:MM
            return time_part
    # HHMMSS format
    if len(s) >= 6 and s.isdigit():
        return f"{s[:2]}:{s[2:4]}"
    # Others: Return as is (maximum 8 characters)
    return s[:8]


def _format_context(
    kanban: dict[str, Any],
    sessions: list[dict[str, str]],
) -> str:
    """Compose Kanban summary + active sessions in markdown format.

    Example output:
        ## Kanban snapshot (automatic injection, user turn point)
        - Open: 1 case, In Progress: 1 case, Review: 6 cases / To Do: 41 cases, Done: 358 cases

        ### Open / In Progress Details



        ### Active Session

    """
    counts = kanban.get("counts", {})
    details = kanban.get("details", [])

    open_c = counts.get("open", 0)
    progress_c = counts.get("progress", 0)
    review_c = counts.get("review", 0)
    todo_c = counts.get("todo", 0)
    done_c = counts.get("done", 0)

    lines: list[str] = []
    lines.append("## Kanban snapshot (automatic injection, user turn point)")
    lines.append(
        f"- Open: {open_c} cases, In Progress: {progress_c} cases, Review: {review_c} cases"
        f"/ To Do: {todo_c} case, Done: {done_c} case"
    )

    # Open / In Progress Details
    if details:
        # Maximum MAX_DETAIL_ITEMS item limit
        display_details = details[:MAX_DETAIL_ITEMS]
        lines.append("")
        lines.append("### Open / In Progress Details")
        for item in display_details:
            number = item.get("number", "")
            title = item.get("title", "")
            status = item.get("status", "")
            label = "In Progress" if "progress" in status.lower() or "in progress" in status.lower() else status
            lines.append(f"- {number} [{label}] {title}")
        if len(details) > MAX_DETAIL_ITEMS:
            lines.append(f"_(Show only top {MAX_DETAIL_ITEMS} items, total {len(details)} items)_")

    # active session
    if sessions:
        lines.append("")
        lines.append("### Active sessions")
        for session in sessions:
            ticket = session.get("ticket", "")
            command = session.get("command", "")
            started = _format_hhmm(session.get("started_at", ""))
            time_str = f" ({started})" if started else ""
            lines.append(f"- {ticket} {command}{time_str}")

    return "\n".join(lines)


# ── Main ─────────────────────────────────────────────────────────────────────────

def build_context(project_root: str | None = None) -> str:
    """Build Kanban + session snapshot context text.

    An entry point that can be called directly from the outside (can be imported from the W03 dispatcher).

    Args:
        project_root: Main repo root path. If None, auto-discovery.

    Returns:
        Context text in markdown format. Empty string on failure.
    """
    if project_root is None:
        project_root = _find_project_root()

    kanban = _collect_kanban_summary(project_root)
    sessions = _collect_active_sessions(project_root)
    return _format_context(kanban, sessions)


def main() -> None:
    """UserPromptSubmit hook context builder main function.

    stdin: UserPromptSubmit JSON payload (ignore content)
    stdout: {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": "<text>"}}
    exit code: always 0 (no blocking of user turn)

    0.8s soft deadline: partial payload output when exceeded.
    When the payload exceeds 4096 chars, Open/In Progress details are only available for the top 10 cases.
    """
    start_time = time.monotonic()

    # When the soft deadline is exceeded, partial output is performed using SIGALRM and then terminates.
    # (SIGALRM is for Unix only)
    deadline_hit = [False]

    def _on_deadline(_signum: int, _frame: Any) -> None:
        deadline_hit[0] = True

    try:
        if hasattr(signal, 'SIGALRM'):
            signal.signal(signal.SIGALRM, _on_deadline)
            # 0.8s + margin 0.05s (float → int rounded up)
            signal.setitimer(signal.ITIMER_REAL, SOFT_DEADLINE)
    except Exception:
        pass

    try:
        # Read stdin (contents can be ignored, but quickly without blocks)
        _stdin_raw = sys.stdin.buffer.read()

        if deadline_hit[0]:
            sys.exit(0)

        project_root = _find_project_root()

        if deadline_hit[0]:
            sys.exit(0)

        context_text = build_context(project_root)

        if deadline_hit[0] and not context_text:
            sys.exit(0)

        # Trimming when payload exceeds 4096 chars
        if len(context_text) > MAX_PAYLOAD_CHARS:
            context_text = context_text[:MAX_PAYLOAD_CHARS] + "\n _(trimmed)_"

        elapsed = time.monotonic() - start_time
        if elapsed > SOFT_DEADLINE and not context_text:
            sys.exit(0)

        output = {
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": context_text,
            }
        }

        sys.stdout.write(json.dumps(output, ensure_ascii=False))
        sys.stdout.flush()

    except Exception:
        # Guaranteed empty stdout + exit 0 on any exception
        pass
    finally:
        # SIGALRM OFF
        try:
            if hasattr(signal, 'SIGALRM'):
                signal.setitimer(signal.ITIMER_REAL, 0)
                signal.signal(signal.SIGALRM, signal.SIG_DFL)
        except Exception:
            pass

    sys.exit(0)


if __name__ == '__main__':
    main()
