"""SyncHandlerMixin — restart + workflow_sync endpoints."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time

from .._common import _workflow_sync_lock, _WORKFLOW_SYNC_URL, api_endpoint, logger


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

    @api_endpoint("W1", "sync")
    def _handle_workflow_sync(self) -> None:
        """POST /api/workflow/sync — init-claude-workflow.sh 실행을 SSE로 스트리밍한다.

        method: POST
        url: /api/workflow/sync
        domain: W1
        handler: SyncHandlerMixin._handle_workflow_sync
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

        # SSE 헤더 송신 — 실패 시 락 즉시 해제
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
            """SSE 프레임을 하나 써 넣는다. 성공 시 True, 연결 끊김 시 False."""
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
                    # 클라이언트 연결 끊김 — 프로세스 종료 후 루프 탈출
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
                    'message': '동기화 완료. 서버 재시작이 필요합니다.',
                    'ts': time.time(),
                })
            else:
                _sse('error', {
                    'exitCode': exit_code,
                    'message': '동기화 실패',
                    'ts': time.time(),
                })
        except Exception as exc:  # noqa: BLE001
            logger.exception('workflow sync failed: %s', exc)
            _sse('error', {
                'exitCode': -1,
                'message': f'내부 오류: {exc}',
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
