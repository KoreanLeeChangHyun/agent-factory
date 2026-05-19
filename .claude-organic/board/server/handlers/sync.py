"""SyncHandlerMixin — restart + debug-log endpoints.

T-513 P5 — `_handle_workflow_sync` 분기는 handlers/settings.py 의
`_handle_settings_workflow_sync` 로 통째 이전 (P2 신설 후 alias 제거 시점).
본 모듈은 restart + debug-log endpoint 만 보존.
"""

from __future__ import annotations

import json
import os
import sys
import threading

from .._common import api_endpoint, logger


class SyncHandlerMixin:
    """Restart and workflow sync handlers."""

    @api_endpoint("SYS", "debug_log")
    def _handle_debug_log(self) -> None:
        """클라 debugLog 이벤트를 서버 파일에 적재한다 (플래그 게이트).

        method: POST
        url: /api/debug-log
        domain: SYS
        handler: SyncHandlerMixin._handle_debug_log
        request: body {ts: iso, tag: str, data: any}
        response_ok: {ok: true, logged: bool}
        response_error: 400 (invalid JSON) / 500 (IO error)
        status_codes: 200, 400, 500
        auth: none (local-only)
        side_effects: append NDJSON to .claude-organic/runs/bg/debug.log (gated by debug.enabled flag)
        sse_events: none
        """
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length) if content_length else b''

        project_root = os.getcwd()
        log_dir = os.path.join(project_root, '.claude-organic', 'runs', 'bg')
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
        """서버 재시작 요청을 처리한다.

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
                project_root, '.claude-organic', '.board.url',
            )
            try:
                os.remove(url_file)
            except OSError:
                pass
            # 서버 진입점은 board/server.py (shim). __file__은 handlers/sync.py이므로
            # 상대 경로로 엔트리 스크립트를 역산한다.
            entry_script = os.path.normpath(
                os.path.join(os.path.dirname(__file__), '..', '..', 'server.py')
            )
            # execv로 프로세스를 교체 — 소켓이 자동 해제되어 포트 충돌 없음
            os.execv(sys.executable, [sys.executable, entry_script, '--serve', project_root])

        threading.Timer(0.3, _do_restart).start()

    # T-513 P5 — `_handle_workflow_sync` 분기는 handlers/settings.py 의
    # `_handle_settings_workflow_sync` 로 통째 이전됨. 본 mixin 은 restart +
    # debug-log endpoint 만 보존.
