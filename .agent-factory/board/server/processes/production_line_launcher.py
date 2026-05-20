"""production-line launcher — `flow-wf submission` subprocess spawn + reader thread charge module.

T-500: separated from the kanban.py ` handle kanban submit` body. handler input validation +
`spawn production line()` commission + JSON response only, and this module is Popen / env injection /
LAUNCH PENDING + LAUNCH STARTED LAUNCH / reader thread spawn

Terms and Conditions:
  - `spawn_production_line(ticket, command) -> dict`:
      * No input validation (reporter responsibility).
      * registry key + session id pre-issued.
      * V2 BOARD POST=true + V2 REGISTRY KEY automatic injection.
      * `flow-wf submit <ticket>` Popen.
      * LAUNCH PENDING + LAUNCH STARTED Launch.
      * thread spawn + ` LAUNCH READER THREADS` registered.
      * Return: `{ok, status, ticket, command, submission at, session id}` (Property) /
              `{ok: False, error kind, message}` (fail).
  - `_production_line_reader_loop(proc, ticket, command, submitted_at)`:
      * `proc.communicate` wait.
      * rc != 0 LAUNCH FAILED LAUNCH(rc == 0 silver driver workflow.finish SSE processing).
      *Remove thread itself from ` LAUNCH READER THREADS`.

Original Position: handlers/kanban.py:194-244 + 510-610 (T-500 before).
"""

from __future__ import annotations

import os
import subprocess
import threading
from datetime import datetime, timezone


# When Popen.communicate ends thread itself removes itself from finally.
# v1 ` launch reader loop` (kanban.py) share the same set — in kanban.py
# `from board.server.processes.production_line_launcher import _LAUNCH_READER_THREADS, _LAUNCH_READER_LOCK`
# import.
_LAUNCH_READER_THREADS: set[threading.Thread] = set()
_LAUNCH_READER_LOCK: threading.Lock = threading.Lock()


def _now_utc() -> datetime:
    """`datetime.now(timezone.utc)` thin wrapper — enter the monkeypatch in the test."""
    return datetime.now(timezone.utc)


def _emit_launch_event_safe(event: str, ticket: str, **kwargs: object) -> None:
    """`engine.apps.board_api.kanban._emit_launch_event` lazy import wrapper.

    Module top-level import kanban
    import module top. emits itself absorbs broadcasting failure.
    """
    try:
        from engine.apps.board_api.kanban import _emit_launch_event
    except ImportError:  # Defending — this import failure is an environmental problem
        return
    _emit_launch_event(event, ticket, **kwargs)


def spawn_production_line(ticket: str, command: str) -> dict:
    """'flow-wf submission <ticket>` subprocess spawn + LAUNCH PENDING/STARTED launch.

    kanban handler is only pre-programmed for ticket / command validation
    If you call this function, you can send the return dict to ` send json`.

    Args:
        ticket: T-NNN
        command: implement|research|review

    Returns:
        success: `{"ok": true, "status": "starting", "ticket", "command",
                "submitted_at": <iso>, "session_id": <wf-T-NNN-key>}`
        failed: `{"ok": False, "error kind": "flow wf not found",
                "message": <str>}`
    """
    project_root = os.getcwd()
    flow_wf = os.path.join(project_root, '.agent-factory', 'bin', 'flow-wf')

    submitted_at = _now_utc()
    registry_key = submitted_at.strftime('%Y%m%d-%H%M%S')
    production_line_session_id = f'wf-{ticket}-{registry_key}'

    env = dict(os.environ)
    env['V2_BOARD_POST'] = 'true'
    env['V2_REGISTRY_KEY'] = registry_key

    try:
        proc = subprocess.Popen(
            [flow_wf, 'submit', ticket],
            cwd=project_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True,
        )
    except FileNotFoundError:
        return {
            'ok': False,
            'error_kind': 'flow_wf_not_found',
            'message': f'flow-wf not found: {flow_wf}',
        }
    except OSError as exc:
        return {
            'ok': False,
            'error_kind': 'popen_failed',
            'message': f'flow-wf Popen failed: {exc!r}',
        }

    # LAUNCH PENDING — right after Popen, HTTP 200 responses.
    _emit_launch_event_safe(
        'LAUNCH_PENDING', ticket,
        command=command,
        submitted_at=submitted_at.isoformat(),
        session_id=production_line_session_id,
    )

    # LAUNCH STARTED — production-line spawn success = cycle entry guarantee.
    spawn_elapsed_ms = int(
        (_now_utc() - submitted_at).total_seconds() * 1000
    )
    _emit_launch_event_safe(
        'LAUNCH_STARTED', ticket,
        session_id=production_line_session_id,
        mode='production_line',
        spawn_duration_ms=spawn_elapsed_ms,
        command=command,
    )

    # reader thread — LAUNCH FAILED emit (regression detection) when driver abnormal termination.
    reader = threading.Thread(
        target=_production_line_reader_loop,
        args=(proc, ticket, command, submitted_at),
        name=f'production-line-reader-{ticket}',
        daemon=True,
    )
    with _LAUNCH_READER_LOCK:
        _LAUNCH_READER_THREADS.add(reader)
    reader.start()

    return {
        'ok': True,
        'status': 'starting',
        'ticket': ticket,
        'command': command,
        'submitted_at': submitted_at.isoformat(),
        'session_id': production_line_session_id,
    }


def _production_line_reader_loop(
    proc: subprocess.Popen,
    ticket: str,
    command: str,
    submitted_at: datetime,
) -> None:
    """rc != 0 when LAUNCH FAILED emitter when finished production-line subprocess.

    v1 ` launch reader loop` (kanban.py) and difference:
      - LAUNCH STARTED Launch X (submit handler launches immediately after Popen).
      - rc == 0 (normal completion) is handled by the driver itself SSE (workflow.finish).
      - rc != 0 (crash) Only LAUNCH FAILED Launch (regression detection).

    Remove thread handle set itself from the last block (GC leak protection).
    """
    self_thread = threading.current_thread()
    try:
        try:
            stdout, stderr = proc.communicate(timeout=None)
        except Exception as exc:
            elapsed_ms = int(
                (_now_utc() - submitted_at).total_seconds() * 1000
            )
            _emit_launch_event_safe(
                'LAUNCH_FAILED', ticket,
                reason='reader_loop_exception',
                returncode=None,
                error_message=repr(exc),
                elapsed_ms=elapsed_ms,
                command=command,
            )
            return

        rc = proc.returncode
        if rc == 0:
            return  # Normal finished — driver workflow.finish SSE is processed.

        elapsed_ms = int(
            (_now_utc() - submitted_at).total_seconds() * 1000
        )
        _emit_launch_event_safe(
            'LAUNCH_FAILED', ticket,
            reason='driver_nonzero_exit',
            returncode=rc,
            error_message=(stderr or '')[:500],
            elapsed_ms=elapsed_ms,
            command=command,
        )
    finally:
        with _LAUNCH_READER_LOCK:
            _LAUNCH_READER_THREADS.discard(self_thread)
