"""SyncHandlerMixin — restart + debug-log endpoints.

T-513 P5 — The `_handle_workflow_sync` branch in handlers/settings.py
Completely transferred to `_handle_settings_workflow_sync` (when alias was removed after P2 was newly established).
This module preserves only the restart + debug-log endpoint.
"""

from __future__ import annotations

import json
import os
import sys
import threading

from board.server.support.common import api_endpoint, logger


class SyncHandlerMixin:
    """Restart and workflow sync handlers."""

    @api_endpoint("SYS", "debug_log")
    def _handle_debug_log(self) -> None:
        """Load client debugLog events to server file (flag gate).

        method: POST
        url: /api/debug-log
        domain: SYS
        handler: SyncHandlerMixin._handle_debug_log
        request: body {ts: iso, tag: str, data: any}
        response_ok: {ok: true, logged: bool}
        response_error: 400 (invalid JSON) / 500 (IO error)
        status_codes: 200, 400, 500
        auth: none (local-only)
        side_effects: append NDJSON to .agent-factory/runs/bg/debug.log (gated by debug.enabled flag)
        sse_events: none
        """
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length) if content_length else b''

        project_root = os.getcwd()
        log_dir = os.path.join(project_root, '.agent-factory', 'runs', 'bg')
        flag_path = os.path.join(log_dir, 'debug.enabled')
        if not os.path.exists(flag_path):
            self._send_json({'ok': True, 'logged': False})
            return

        try:
            entry = json.loads(body) if body else {}
        except (ValueError, json.JSONDecodeError):
            self.send_response(400)
            self.end_headers()
            return
        try:
            os.makedirs(log_dir, exist_ok=True)
            with open(os.path.join(log_dir, 'debug.log'), 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')
        except OSError as exc:
            logger.error("debug-log write fail: %s", exc)
            self.send_response(500)
            self.end_headers()
            return
        self._send_json({'ok': True, 'logged': True})

    @api_endpoint("SYS", "restart")
    def _handle_restart(self) -> None:
        """Processes server restart requests.

        method: POST
        url: /api/restart
        domain: SYS
        handler: SyncHandlerMixin._handle_restart
        request: body none
        response_ok: {ok: true}
        response_error: n/a (always succeeds before exec)
        status_codes: 200
        auth: none (local-only) — user-triggered
        side_effects: remove .board.url, execv new server process
        sse_events: none
        """
        self._send_json({'ok': True})

        def _do_restart() -> None:
            project_root = os.getcwd()
            url_file = os.path.join(
                project_root, '.agent-factory', '.board.url',
            )
            try:
                os.remove(url_file)
            except OSError:
                pass
            entry_script = os.path.join(project_root, '.agent-factory', 'board', 'server.py')
            # Replace process with execv — sockets are automatically released so no port conflicts
            os.execv(sys.executable, [sys.executable, entry_script, '--serve', project_root])

        threading.Timer(0.3, _do_restart).start()

    # T-513 P5 — The `_handle_workflow_sync` branch in handlers/settings.py
    # Moved entirely to `_handle_settings_workflow_sync`. This mixin restart +
    # Only debug-log endpoints are preserved.
