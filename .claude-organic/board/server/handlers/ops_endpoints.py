"""OpsHandlerMixin — INF domain endpoints (T-511 P5).

운영 endpoint 3건:
  - POST /api/ops/zombie-reap   — Claude CLI 좀비 회수 명시 호출 (T-403 GC 사이드카 진입점)
  - POST /api/ops/debug-toggle  — debug.enabled 플래그 토글 (`true|false` body)
  - GET  /api/ops/sse-status    — 3 SSE 채널 (SSEClientManager / TerminalSSEChannel / V2WorkflowSSEChannel)
                                  클라이언트 수 + 마지막 이벤트 시각

본 endpoint 들은 외부 도구 / 사용자 명시 호출 진입점이다. 자동 사이드카가 같은
기능을 결정론적으로 수행하는 영역 (T-403 GC daemon thread 등) 도 본 endpoint
로 즉시 트리거 가능 — debug / recovery / operator 진입로 일관화.
"""

from __future__ import annotations

import os
import time

from .._common import api_endpoint, logger


class OpsHandlerMixin:
    """INF domain — operator-facing diagnostic / recovery endpoints."""

    @api_endpoint("INF", "zombie_reap")
    def _handle_ops_zombie_reap(self) -> None:
        """POST /api/ops/zombie-reap — Claude CLI 좀비 subprocess 회수 명시 호출.

        T-403 GC 사이드카 daemon thread 가 결정론적으로 동일 작업을 60s 주기로
        수행한다. 본 endpoint 는 사용자/외부 도구가 즉시 트리거하는 명시 진입점.

        구현: `os.waitpid(-1, os.WNOHANG)` 루프로 종료된 자식 reap. 평소 비용 0
        (os 호출 한 번 + 빈 루프).

        method: POST
        url: /api/ops/zombie-reap
        domain: INF
        handler: OpsHandlerMixin._handle_ops_zombie_reap
        request: body none
        response_ok: {ok: true, reaped: int, ts: float}
        response_error: n/a (always 200 / 500 on os error)
        status_codes: 200, 500
        auth: none (local-only) — operator trigger
        side_effects: os.waitpid 호출로 좀비 자식 회수 (state.py 영향 X)
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
            # waitpid 가 자식 없을 때 발생 — 정상 종료
            pass
        except OSError as exc:
            logger.error('zombie-reap failed: %s', exc)
            self._send_error(500, f'zombie-reap failed: {exc}')
            return

        self._send_json({'ok': True, 'reaped': reaped, 'ts': time.time()})

    @api_endpoint("INF", "debug_toggle")
    def _handle_ops_debug_toggle(self) -> None:
        """POST /api/ops/debug-toggle — debug.enabled 플래그 토글.

        본문 `{enabled: true|false}` 또는 body 없을 시 현재 상태 토글.
        플래그 파일 (.claude-organic/runs/bg/debug.enabled) 생성/삭제로
        debug.log NDJSON 적재 활성/비활성 게이트.

        method: POST
        url: /api/ops/debug-toggle
        domain: INF
        handler: OpsHandlerMixin._handle_ops_debug_toggle
        request: body {enabled?: bool} (생략 시 자동 토글)
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
        bg_dir = os.path.join(project_root, '.claude-organic', 'runs', 'bg')
        flag_path = os.path.join(bg_dir, 'debug.enabled')

        try:
            os.makedirs(bg_dir, exist_ok=True)
        except OSError as exc:
            self._send_error(500, f'mkdir failed: {exc}')
            return

        currently_enabled = os.path.exists(flag_path)

        if requested is None:
            # 자동 토글
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
        """GET /api/ops/sse-status — 3 SSE 채널 클라이언트 수 + 마지막 이벤트 시각.

        SSEClientManager (server-wide) + TerminalSSEChannel (메인 터미널) +
        V2WorkflowSSEChannel (per-session N) 각각의 라이브 클라이언트 수 dump.

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
        from ..state import sse_manager, terminal_sse_channel, v2_workflow_registry

        # SSEClientManager (server-wide singleton)
        try:
            sse_clients = sse_manager.client_count
        except Exception:  # noqa: BLE001
            sse_clients = -1

        # TerminalSSEChannel (메인 터미널)
        try:
            terminal_clients = terminal_sse_channel.client_count
        except Exception:  # noqa: BLE001
            terminal_clients = -1

        # V2WorkflowSSEChannel — per-session
        v2_sessions: list[dict] = []
        try:
            for meta in v2_workflow_registry.list_all():
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
