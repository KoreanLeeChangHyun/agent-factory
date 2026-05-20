"""State transition, context update, and session link modules.

Provides state-related business logic separated from update_state.py.

Scope of responsibility:
    - Print state transition banner (_print_state_banner)
    - Update .context.json agent field (update_context)
    - status.json FSM status transition (update_status)
    - status.json session link management (link_session)

Main functions:
    _print_state_banner: Prints the state transition banner in 2-line format.
    update_context: Update agent field in .context.json
    update_status: status.json status transition + FSM verification
    link_session: status.json Add session to linked_sessions array
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any

# Ensure sys.path: add scripts/ directory to path
_engine_dir = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
)
if _engine_dir not in sys.path:
    sys.path.insert(0, _engine_dir)

from common import (  # noqa: E402
    atomic_write_json,
    load_json_file,
)
from constants import FSM_TRANSITIONS, KST  # noqa: E402
from flow.flow_logger import append_log as _append_log  # noqa: E402

# history_sync.py absolute path
HISTORY_SYNC_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "sync",
    "history_sync.py",
)

# Project root (to resolve .board.url location)
_PROJECT_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..")
)


def _resolve_board_port() -> int | None:
    """Interprets the Board server port.

    In the `_WF_SERVER_PORT` environment variable or `.agent-factory/.board.url` file
    Extract the port number. If neither exists, None is returned.
    """
    port_env = os.environ.get("_WF_SERVER_PORT")
    if port_env:
        try:
            return int(port_env)
        except ValueError:
            pass
    board_url_path = os.path.join(_PROJECT_ROOT, ".agent-factory", ".board.url")
    try:
        with open(board_url_path, "r", encoding="utf-8") as f:
            url = f.read().strip()
        if "://" in url:
            host_part = url.split("://", 1)[1]
            host_port = host_part.split("/")[0]
            if ":" in host_port:
                return int(host_port.split(":")[1])
    except (OSError, ValueError):
        pass
    return None


def _notify_board_step(to_step: str, abs_work_dir: str = "") -> None:
    """Notifies the Board server of the workflow step transition (best-effort).

    Obtain ticket_id from the `_WF_TICKET_ID` environment variable and send it to `/terminal/workflow/list`
    After retrieving the session_id, call `/terminal/workflow/step` POST.
    If the server does not start, there is no matching session, or a network error occurs, it passes quietly.

    It does not block workflow progress, and all exceptions are ignored, leaving only a log.

    Args:
        to_step: Transition target step name (converted to lowercase and used as emit_step argument).
        abs_work_dir: Workflow work directory (for logging, omit logging if empty).
    """
    try:
        port = _resolve_board_port()
        if port is None:
            return
        ticket_id = os.environ.get("_WF_TICKET_ID", "").strip()
        if not ticket_id:
            return

        list_url = f"http://127.0.0.1:{port}/terminal/workflow/list"
        with urllib.request.urlopen(list_url, timeout=2) as resp:
            sessions = json.loads(resp.read().decode("utf-8"))
        sessions_iter = sessions if isinstance(sessions, list) else sessions.get("sessions", [])
        # Since there may be multiple sessions on the same ticket, the latest matching based on created_at is selected.
        # Priority is given to active (non-stopped) sessions, and if there is no activity, it falls back to the latest stopped session.
        candidates = [
            s for s in sessions_iter
            if isinstance(s, dict) and s.get("ticket_id") == ticket_id and s.get("session_id")
        ]
        if not candidates:
            return
        active = [s for s in candidates if s.get("status") != "stopped"]
        pool = active if active else candidates
        chosen = max(pool, key=lambda s: s.get("created_at", ""))
        session_id = chosen.get("session_id", "") or ""
        if not session_id:
            return

        body = json.dumps({
            "session_id": session_id,
            "step": to_step.lower(),
            "detail": {"trigger": "state_transition"},
        }, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/terminal/workflow/step",
            data=body,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=2) as post_resp:
            post_resp.read()

        if abs_work_dir:
            _append_log(
                abs_work_dir,
                "INFO",
                f"BOARD_STEP_NOTIFY: ticket={ticket_id} session={session_id} step={to_step.lower()}",
            )
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError) as exc:
        if abs_work_dir:
            _append_log(abs_work_dir, "WARN", f"board step notify failed: {exc}")


def _print_state_banner(
    from_step: str, to_step: str, abs_work_dir: str = ""
) -> None:
    """The state transition banner is output in a two-line format.

    Args:
        from_step: Previous step name (e.g. 'PLAN', 'WORK')
        to_step: Next step name (e.g. 'WORK', 'REPORT')
        abs_work_dir: Absolute path to work directory (for log recording, omit log if empty string)
    """
    line1 = "[STATE] Change stage"
    line2 = f">> {from_step} -> {to_step}"
    print(line1, flush=True)
    print(line2, flush=True)
    if abs_work_dir:
        _append_log(abs_work_dir, "INFO", line1)
        _append_log(abs_work_dir, "INFO", line2)


def update_context(local_context: str, agent: str) -> str:
    """Only update the agent field in context.json.

    Args:
        local_context: Absolute path to the .context.json file
        agent: Agent name to set

    Returns:
        Processing result string. Example: 'context -> agent=orchestrator',
        'context -> skipped (file not found)', 'context -> failed'.
    """
    if not os.path.exists(local_context):
        print(f"[WARN] .context.json not found: {local_context}", file=sys.stderr)
        return "context -> skipped (file not found)"

    try:
        data = load_json_file(local_context)
        if data is None:
            print(f"[WARN] .context.json read failed: {local_context}", file=sys.stderr)
            return "context -> skipped (read failed)"

        data["agent"] = agent
        atomic_write_json(local_context, data)
        _append_log(os.path.dirname(local_context), "INFO", f"Context updated: agent={agent}")
        return f"context -> agent={agent}"
    except Exception as e:
        print(f"[WARN] .context.json update failed ({local_context}): {e}", file=sys.stderr)
        return "context -> failed"


def update_status(
    abs_work_dir: str, status_file: str, from_step: str, to_step: str
) -> str:
    """Update status.json and synchronize registry steps.

    FSM verification logic:
      1. Skip verification if the WORKFLOW_SKIP_GUARD=1 environment variable is set.
      2. Check current_step: Verify that the current step and from_step in status.json match.
      3. Check allowed: In FSM_TRANSITIONS(constants.py), check what is allowed in current mode/from_step.
         Query the target list and verify that it contains to_step

    Non-blocking principle:
      Even if FSM verification fails, the process is not terminated (always exit 0).

    Call method:
      When calling CLI, from_step is automatically read from status.json.
      When calling the library, from_step must be explicitly passed.

    Args:
        abs_work_dir: Absolute path to work directory
        status_file: status.json file path
        from_step: name of transition start step
        to_step: Transition target step name

    Returns:
        Processing result string. Example: 'status -> PLAN->WORK',
        'status -> FSM guard blocked (reason: ...)',
        'status -> skipped (file not found)', 'status -> failed'.
    """
    skip_guard = os.environ.get("WORKFLOW_SKIP_GUARD", "") == "1"

    if not os.path.exists(status_file):
        print(f"[WARN] status.json not found: {status_file}", file=sys.stderr)
        _append_log(abs_work_dir, "WARN", f"status.json not found: {status_file}")
        return "status -> skipped (file not found)"

    try:
        data = load_json_file(status_file)
        if data is None:
            print(f"[WARN] status.json read failed: {status_file}", file=sys.stderr)
            _append_log(abs_work_dir, "WARN", f"status.json read failed: {status_file}")
            return "status -> skipped (read failed)"

        # Idempotent same-step transition: Transition to the same step is silent skip.
        # Blocks accumulated noise such as finalize duplicate calls (DONE → DONE 23 times).
        # In log analysis (2026-04-29), DONE→DONE / PLAN→PLAN / WORK→WORK, etc.
        # Cases where same-step transitions were accumulated in the ERROR log were handled as normal no action.
        if from_step == to_step:
            _append_log(
                abs_work_dir,
                "INFO",
                f"FSM idempotent: already at {to_step}, transition skipped.",
            )
            return f"status -> idempotent (already at {to_step})"

        # FSM transition verification
        if skip_guard:
            print(
                f"[AUDIT] WORKFLOW_SKIP_GUARD active: {from_step}->{to_step}",
                file=sys.stderr,
                flush=True,
            )
            _append_log(
                abs_work_dir,
                "AUDIT",
                f"WORKFLOW_SKIP_GUARD active: {from_step}->{to_step}",
            )
        else:
            current_step = (
                data.get("workflow_phase")
                or data.get("step")          # legacy status.json (pre
                or data.get("phase", "NONE") # legacy status.json (pre
            )
            workflow_mode = data.get("mode", "full").lower()

            # Allowed_targets is required for error messages in both verifications, so check it in advance.
            allowed_table = FSM_TRANSITIONS.get(
                workflow_mode,
                FSM_TRANSITIONS.get("multi", FSM_TRANSITIONS.get("full", {})),
            )
            allowed = allowed_table.get(current_step, [])

            if from_step != current_step:
                print(
                    f"[ERROR] FSM guard: from_step mismatch. "
                    f"from_step={from_step}, to_step={to_step}, "
                    f"current_step={current_step}, workflow_mode={workflow_mode}, "
                    f"allowed_targets={allowed}. transition blocked.",
                    file=sys.stderr,
                )
                _append_log(
                    abs_work_dir,
                    "ERROR",
                    f"FSM guard: from_step mismatch. from_step={from_step}, to_step={to_step}, "
                    f"current_step={current_step}, workflow_mode={workflow_mode}, "
                    f"allowed_targets={allowed}. transition blocked.",
                )
                return (
                    f"status -> FSM guard blocked "
                    f"(reason: from_step mismatch, expected={current_step}, got={from_step}, "
                    f"workflow_mode={workflow_mode}, allowed_targets={allowed})"
                )

            if to_step not in allowed:
                print(
                    f"[ERROR] FSM guard: illegal transition {from_step}->{to_step}. "
                    f"current_step={current_step}, workflow_mode={workflow_mode}, "
                    f"allowed_targets={allowed}. transition blocked.",
                    file=sys.stderr,
                )
                _append_log(
                    abs_work_dir,
                    "ERROR",
                    f"FSM guard: illegal transition {from_step}->{to_step}. "
                    f"current_step={current_step}, workflow_mode={workflow_mode}, "
                    f"allowed_targets={allowed}. transition blocked.",
                )
                return (
                    f"status -> FSM guard blocked "
                    f"(reason: illegal transition {from_step}->{to_step}, "
                    f"workflow_mode={workflow_mode}, allowed_targets={allowed})"
                )

        # KST time
        kst = KST
        now = datetime.now(kst).strftime("%Y-%m-%dT%H:%M:%S+09:00")

        data["workflow_phase"] = to_step
        data["updated_at"] = now

        if "transitions" not in data:
            data["transitions"] = []
        data["transitions"].append({"from": from_step, "to": to_step, "at": now})

        atomic_write_json(status_file, data)
        _append_log(abs_work_dir, "INFO", f"State transition: {from_step} -> {to_step}")

        # Notifies the board server of step transition (best-effort, does not block workflow progress in case of failure)
        _notify_board_step(to_step, abs_work_dir)

        # history_sync.py sync call (non-blocking principle: only output a warning in case of failure)
        try:
            subprocess.run(
                ["python3", HISTORY_SYNC_PATH, "sync"],
                capture_output=True,
                timeout=30,
            )
        except Exception as e:
            print(f"[WARN] history sync failed: {e}", file=sys.stderr)
            _append_log(abs_work_dir, "WARN", f"history sync failed: {e}")

        # No ANSI code in return value (banner is handled by _print_state_banner())
        result = f"status -> {from_step}->{to_step}"
    except Exception as e:
        print(f"[WARN] status.json update failed: {e}", file=sys.stderr)
        _append_log(abs_work_dir, "WARN", f"status.json update failed: {e}")
        return "status -> failed"

    return result


def link_session(status_file: str, session_id: str) -> str:
    """Add the session ID to the linked_sessions array in status.json.

    Args:
        status_file: status.json file path
        session_id: Claude session ID to register

    Returns:
        Processing result string. Example: 'link-session -> added: abc123 (total: 2)',
        'link-session -> already linked: abc123',
        'link-session -> skipped (empty)', 'link-session -> failed'.
    """
    if not session_id:
        print("[WARN] link-session: sessionId is empty so ignored.", file=sys.stderr)
        return "link-session -> skipped (empty)"

    if not os.path.exists(status_file):
        print(f"[WARN] status.json not found: {status_file}", file=sys.stderr)
        return "link-session -> skipped (file not found)"

    try:
        data = load_json_file(status_file)
        if data is None:
            return "link-session -> skipped (read failed)"

        if "linked_sessions" not in data or not isinstance(
            data.get("linked_sessions"), list
        ):
            data["linked_sessions"] = []

        if session_id in data["linked_sessions"]:
            return f"link-session -> already linked: {session_id}"

        data["linked_sessions"].append(session_id)
        atomic_write_json(status_file, data)
        count = len(data["linked_sessions"])
        _append_log(
            os.path.dirname(status_file),
            "INFO",
            f"SESSION_LINKED: sessionId={session_id} total={count}",
        )
        return f"link-session -> added: {session_id} (total: {count})"
    except Exception as e:
        print(f"[WARN] link-session failed: {e}", file=sys.stderr)
        return "link-session -> failed"
