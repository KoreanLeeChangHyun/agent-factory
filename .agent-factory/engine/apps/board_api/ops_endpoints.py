"""OpsHandlerMixin — INF domain endpoints (T-511 P5).

3 operational endpoints:
  - POST /api/ops/zombie-reap — Claude CLI zombie retrieval explicit call (T-403 GC sidecar entry point)
  - POST /api/ops/debug-toggle — Toggle debug.enabled flag (`true|false` body)
  - GET /api/ops/sse-status — 3 SSE channels (SSEClientManager / TerminalSSEChannel / ProductionLineSSEChannel)
                                  Number of clients + last event time

These endpoints are entry points for external tool/user specified calls. Automatic sidecar like
This endpoint also includes areas that perform functions deterministically (T-403 GC daemon thread, etc.)
Can be instantly triggered with — consistent debug/recovery/operator ramp.
"""

from __future__ import annotations

import os
import time

from board.server.support.common import api_endpoint, logger


class OpsHandlerMixin:
    """INF domain — operator-facing diagnostic / recovery endpoints."""

    @api_endpoint("INF", "zombie_reap")
    def _handle_ops_zombie_reap(self) -> None:
        """POST /api/ops/zombie-reap — Claude CLI zombie subprocess recall explicit call.

        The T-403 GC sidecar daemon thread deterministically performs the same task in 60s cycle.
        Perform. This endpoint is an explicit entry point that is immediately triggered by the user/external tool.

        Implementation: Child reap terminated with `os.waitpid(-1, os.WNOHANG)` loop. Usual cost 0
        (one os call + empty loop).

        method: POST
        url: /api/ops/zombie-reap
        domain: INF
        handler: OpsHandlerMixin._handle_ops_zombie_reap
        request: body none
        response_ok: {ok: true, reaped: int, ts: float}
        response_error: n/a (always 200 / 500 on os error)
        status_codes: 200, 500
        auth: none (local-only) — operator trigger
        side_effects: Retrieve zombie children by calling os.waitpid (state.py affects X)
        sse_events: none
        """
        reaped = 0
        try:
            while True:
                pid, _status = os.waitpid(-1, os.WNOHANG)
                if pid == 0:
                    break
                reaped += 1
        except ChildProcessError:
            # Occurs when waitpid has no children — graceful shutdown
            pass
        except OSError as exc:
            logger.error('zombie-reap failed: %s', exc)
            self._send_error(500, f'zombie-reap failed: {exc}')
            return

        self._send_json({'ok': True, 'reaped': reaped, 'ts': time.time()})

    @api_endpoint("INF", "debug_toggle")
    def _handle_ops_debug_toggle(self) -> None:
        """POST /api/ops/debug-toggle — Toggle the debug.enabled flag.

        Body `{enabled: true|false}` or toggle the current state if there is no body.
        By creating/deleting the flag file (.agent-factory/runs/bg/debug.enabled)
        debug.log NDJSON load enable/disable gate.

        method: POST
        url: /api/ops/debug-toggle
        domain: INF
        handler: OpsHandlerMixin._handle_ops_debug_toggle
        request: body {enabled?: bool} (automatic toggle if omitted)
        response_ok: {ok: true, enabled: bool, path: str}
        response_error: {ok: false, error: str}
        status_codes: 200, 400, 500
        auth: none (local-only) — operator trigger
        side_effects: create/remove debug.enabled flag file
        sse_events: none
        """
        data = self._read_json_body() or {}
        requested = data.get('enabled')

        project_root = os.getcwd()
        bg_dir = os.path.join(project_root, '.agent-factory', 'runs', 'bg')
        flag_path = os.path.join(bg_dir, 'debug.enabled')

        try:
            os.makedirs(bg_dir, exist_ok=True)
        except OSError as exc:
            self._send_error(500, f'mkdir failed: {exc}')
            return

        currently_enabled = os.path.exists(flag_path)

        if requested is None:
            # auto toggle
            new_state = not currently_enabled
        elif isinstance(requested, bool):
            new_state = requested
        else:
            self._send_error(400, '"enabled" must be a boolean')
            return

        try:
            if new_state and not currently_enabled:
                with open(flag_path, 'w', encoding='utf-8') as f:
                    f.write('')
            elif not new_state and currently_enabled:
                os.remove(flag_path)
        except OSError as exc:
            self._send_error(500, f'flag toggle failed: {exc}')
            return

        self._send_json({
            'ok': True,
            'enabled': new_state,
            'path': flag_path,
        })

    @api_endpoint("INF", "sse_status")
    def _handle_ops_sse_status(self) -> None:
        """GET /api/ops/sse-status — Number of 3 SSE channel clients + time of last event.

        SSEClientManager (server-wide) + TerminalSSEChannel (main terminal) +
        ProductionLineSSEChannel (per-session N) Dump number of live clients for each.

        method: GET
        url: /api/ops/sse-status
        domain: INF
        handler: OpsHandlerMixin._handle_ops_sse_status
        request: query none
        response_ok: {ok: true, sse_client_manager: {...}, terminal_channel: {...}, v2_sessions: [...]}
        response_error: n/a (always 200)
        status_codes: 200
        auth: none (local-only) — operator trigger
        side_effects: read-only snapshot of SSE channel registries
        sse_events: none
        """
        from ..state import sse_manager, terminal_sse_channel, production_line_registry

        # SSEClientManager (server-wide singleton)
        try:
            sse_clients = sse_manager.client_count
        except Exception:  # noqa: BLE001
            sse_clients = -1

        # TerminalSSEChannel (main terminal)
        try:
            terminal_clients = terminal_sse_channel.client_count
        except Exception:  # noqa: BLE001
            terminal_clients = -1

        # ProductionLineSSEChannel — per-session
        v2_sessions: list[dict] = []
        try:
            for meta in production_line_registry.list_all():
                v2_sessions.append({
                    'session_id': meta.get('session_id'),
                    'ticket_id': meta.get('ticket_id'),
                    'current_step': meta.get('current_step'),
                    'step_ts': meta.get('step_ts'),
                })
        except Exception as exc:  # noqa: BLE001
            logger.error('sse-status v2 list failed: %s', exc)

        self._send_json({
            'ok': True,
            'ts': time.time(),
            'sse_client_manager': {'client_count': sse_clients},
            'terminal_channel': {'client_count': terminal_clients},
            'v2_sessions': v2_sessions,
        })
