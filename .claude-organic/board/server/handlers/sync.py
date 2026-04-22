"""SyncHandlerMixin — restart + workflow_sync endpoints."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import urllib.request

from .._common import _workflow_sync_lock, _WORKFLOW_SYNC_URL, logger


class SyncHandlerMixin:
    """Restart and workflow sync handlers."""

    def _handle_restart(self) -> None:
        """서버 재시작 요청을 처리한다.

        응답을 보낸 뒤 짧은 지연 후 현재 서버 소켓을 해제하고,
        새 서버 프로세스를 생성한 뒤 현재 프로세스를 종료한다.
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
            # execv로 프로세스를 교체 — 소켓이 자동 해제되어 포트 충돌 없음
            os.execv(sys.executable, [sys.executable, __file__, '--serve', project_root])

        threading.Timer(0.3, _do_restart).start()

    def _handle_workflow_sync(self) -> None:
        """POST /api/workflow/sync — init-claude-workflow.sh 실행을 SSE로 스트리밍한다.

        동시 실행은 ``_workflow_sync_lock``으로 차단한다. 락 획득 실패 시 409를
        반환하며, SSE 스트림을 시작하지 않는다. 락 획득 성공 시 SSE 헤더를 내보낸
        뒤 ``curl ... | bash`` 서브프로세스의 stdout을 라인 단위로 ``event: log``
        프레임으로 푸시하고, 종료 코드에 따라 ``event: done`` 또는
        ``event: error``를 마지막으로 보낸다. 클라이언트 disconnect
        (BrokenPipeError 등) 시 서브프로세스를 terminate한다.
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
