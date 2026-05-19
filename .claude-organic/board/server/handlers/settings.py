"""SettingsHandlerMixin — 시스템 부트스트랩/설정 도메인 endpoint.

T-513 P2 — sync.py 의 옛 핸들러를 본 모듈로 이전. v1 워크플로우
엔진 폐기 (T-513) 후 본 endpoint 는 워크플로우 분기가 아닌 시스템 부트스트랩
(`init-claude-workflow.sh` 다운로드/실행) 책임 — 도메인 SETTINGS 정합. 호출
경로는 `/api/settings/workflow-sync` 단일.
"""

from __future__ import annotations

import json
import os
import subprocess
import time

from .._common import _workflow_sync_lock, _WORKFLOW_SYNC_URL, api_endpoint, logger


class SettingsHandlerMixin:
    """시스템 부트스트랩/설정 도메인 endpoint."""

    @api_endpoint("SETTINGS", "workflow_sync")
    def _handle_settings_workflow_sync(self) -> None:
        """POST /api/settings/workflow-sync — init-claude-workflow.sh 실행 SSE 스트림.

        T-513 P2 — sync.py 의 `_handle_workflow_sync` 를 settings 도메인으로 이전.
        본 endpoint 는 v1 워크플로우 엔진 sync 가 아니라 시스템 부트스트랩 (워크
        플로우 인프라 install/upgrade) 책임.

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
            logger.exception('settings workflow-sync failed: %s', exc)
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
