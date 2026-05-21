"""SettingsHandlerMixin — Agent Factory bootstrap/settings domain endpoint.

T-513 P2 — Moved the old handler in sync.py to this module. v1 workflow
engine retirement (T-513) made this endpoint an Agent Factory bootstrap path,
not a workflow branch. It downloads/runs `init.sh` through the fixed
`/api/settings/workflow-sync` route.
"""

from __future__ import annotations

import json
import os
import subprocess
import time

from engine.adapters.git.github_cli import auth_status, start_web_auth
from board.server.support.common import (
    _workflow_sync_lock,
    _WORKFLOW_SYNC_URL,
    api_endpoint,
    logger,
)


class SettingsHandlerMixin:
    """System bootstrap/configuration domain endpoint."""

    @api_endpoint("SETTINGS", "github_auth_status")
    def _handle_settings_github_auth_status(self) -> None:
        """GET /api/settings/github-auth — GitHub CLI auth status."""
        self._send_json(auth_status())

    @api_endpoint("SETTINGS", "github_auth_start")
    def _handle_settings_github_auth_start(self) -> None:
        """POST /api/settings/github-auth — start GitHub CLI web auth."""
        result = start_web_auth()
        status = 200 if result.get("ok") else 503
        if status == 200:
            self._send_json(result)
        else:
            self._send_json_with_status(status, result)

    @api_endpoint("SETTINGS", "workflow_sync")
    def _handle_settings_workflow_sync(self) -> None:
        """POST /api/settings/workflow-sync — init.sh runs SSE stream.

        T-513 P2 — Move `_handle_workflow_sync` in sync.py to the settings domain.
        This endpoint is not a v1 workflow engine sync; it is responsible for
        Agent Factory infrastructure install/upgrade.

        method: POST
        url: /api/settings/workflow-sync
        domain: SETTINGS
        handler: SettingsHandlerMixin._handle_settings_workflow_sync
        request: body none (URL fixed = _WORKFLOW_SYNC_URL)
        response_ok: text/event-stream (start / log / done events)
        response_error: 409 (already running), error event in stream
        status_codes: 200, 409
        auth: none (local-only) — user-triggered
        side_effects: spawn `curl | bash` subprocess; acquire _workflow_sync_lock
        sse_events: SSE inline events (start/log/done/error) — separate from board SSE channels
        """
        if not _workflow_sync_lock.acquire(blocking=False):
            self._send_error(409, 'Sync already in progress')
            return

        try:
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Connection', 'keep-alive')
            self.send_header('X-Accel-Buffering', 'no')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
        except (BrokenPipeError, ConnectionResetError, OSError):
            _workflow_sync_lock.release()
            return

        def _sse(event: str, data: dict) -> bool:
            payload = (
                f'event: {event}\n'
                f'data: {json.dumps(data, ensure_ascii=False)}\n\n'
            )
            try:
                self.wfile.write(payload.encode('utf-8'))
                self.wfile.flush()
                return True
            except (BrokenPipeError, ConnectionResetError, OSError):
                return False

        proc = None
        try:
            _sse('start', {
                'message': 'Starting workflow sync...',
                'url': _WORKFLOW_SYNC_URL,
                'ts': time.time(),
            })

            proc = subprocess.Popen(  # noqa: S603,S607
                ['bash', '-c', f'curl -fsSL {_WORKFLOW_SYNC_URL} | bash'],
                cwd=os.getcwd(),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=1,
                text=True,
            )

            assert proc.stdout is not None
            for line in proc.stdout:
                if not _sse('log', {
                    'line': line.rstrip('\n'),
                    'ts': time.time(),
                }):
                    try:
                        proc.terminate()
                    except OSError:
                        pass
                    break

            proc.wait()
            exit_code = proc.returncode

            if exit_code == 0:
                _sse('done', {
                    'exitCode': 0,
                    'message': 'Synchronization complete. A server restart is required.',
                    'ts': time.time(),
                })
            else:
                _sse('error', {
                    'exitCode': exit_code,
                    'message': 'Sync failed',
                    'ts': time.time(),
                })
        except Exception as exc:  # noqa: BLE001
            logger.exception('settings workflow-sync failed: %s', exc)
            _sse('error', {
                'exitCode': -1,
                'message': f'Internal error: {exc}',
                'ts': time.time(),
            })
        finally:
            if proc is not None and proc.poll() is None:
                try:
                    proc.terminate()
                    proc.wait(timeout=5)
                except (OSError, subprocess.TimeoutExpired):
                    try:
                        proc.kill()
                    except OSError:
                        pass
            _workflow_sync_lock.release()
