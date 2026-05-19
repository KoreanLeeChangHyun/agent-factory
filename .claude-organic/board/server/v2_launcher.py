"""v2 driver launcher — `flow-wf submit` subprocess spawn + reader thread 책임 모듈.

T-500: kanban.py `_handle_kanban_submit` 본체에서 분리. handler 는 입력 validation +
`spawn_v2_driver()` 위임 + JSON 응답만 담당하고, 본 모듈이 Popen / env 주입 /
LAUNCH_PENDING + LAUNCH_STARTED 발사 / reader thread spawn 을 통째 담당한다.

규약 (책임 분담):
  - `spawn_v2_driver(ticket, command) -> dict`:
      * 입력 validation 없음 (호출자 책임).
      * registry_key + session_id 사전 발급.
      * V2_BOARD_POST=true + V2_REGISTRY_KEY 자동 주입.
      * `flow-wf submit <ticket>` Popen.
      * LAUNCH_PENDING + LAUNCH_STARTED 발사.
      * reader thread spawn + `_LAUNCH_READER_THREADS` 등록.
      * 반환: `{ok, status, ticket, command, submitted_at, session_id}` (성공) /
              `{ok: False, error_kind, message}` (실패).
  - `_v2_driver_reader_loop(proc, ticket, command, submitted_at)`:
      * `proc.communicate()` 대기.
      * rc != 0 일 때만 LAUNCH_FAILED 발사 (rc == 0 은 driver workflow.finish SSE 가 처리).
      * finally 에서 thread 자기 자신을 `_LAUNCH_READER_THREADS` 에서 제거.

원래 위치: handlers/kanban.py:194-244 + 510-610 (T-500 이전).
"""

from __future__ import annotations

import os
import subprocess
import threading
from datetime import datetime, timezone


# Popen.communicate 종료 시 thread 자체가 finally 에서 자기 자신을 제거한다.
# v1 `_launch_reader_loop` (kanban.py) 도 동일 set 을 공유한다 — kanban.py 에서
# `from board.server.v2_launcher import _LAUNCH_READER_THREADS, _LAUNCH_READER_LOCK`
# 로 import 한다.
_LAUNCH_READER_THREADS: set[threading.Thread] = set()
_LAUNCH_READER_LOCK: threading.Lock = threading.Lock()


def _now_utc() -> datetime:
    """`datetime.now(timezone.utc)` thin wrapper — 테스트에서 monkeypatch 진입점."""
    return datetime.now(timezone.utc)


def _emit_launch_event_safe(event: str, ticket: str, **kwargs: object) -> None:
    """`handlers.kanban._emit_launch_event` lazy import wrapper.

    Module top-level import 로 circular import 위험을 차단 (handlers.kanban
    이 본 모듈을 module top 에서 import). emit 자체가 broadcast 실패를 흡수.
    """
    try:
        from board.server.handlers.kanban import _emit_launch_event
    except ImportError:  # 방어적 — 본 import 실패는 환경 문제
        return
    _emit_launch_event(event, ticket, **kwargs)


def spawn_v2_driver(ticket: str, command: str) -> dict:
    """`flow-wf submit <ticket>` subprocess spawn + LAUNCH_PENDING/STARTED 발사.

    호출자 (kanban handler) 는 ticket / command validation 만 사전 수행하고
    본 함수를 호출한 뒤 반환 dict 를 그대로 `_send_json` 에 전달하면 된다.

    Args:
        ticket: T-NNN
        command: implement|research|review

    Returns:
        성공: `{"ok": True, "status": "starting", "ticket", "command",
                "submitted_at": <iso>, "session_id": <wf-T-NNN-key>}`
        실패: `{"ok": False, "error_kind": "flow_wf_not_found"|"popen_failed",
                "message": <str>}`
    """
    project_root = os.getcwd()
    flow_wf = os.path.join(project_root, '.claude-organic', 'bin', 'flow-wf')

    submitted_at = _now_utc()
    registry_key = submitted_at.strftime('%Y%m%d-%H%M%S')
    v2_session_id = f'wf-{ticket}-{registry_key}'

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

    # LAUNCH_PENDING — Popen 직후, HTTP 200 응답 직전.
    _emit_launch_event_safe(
        'LAUNCH_PENDING', ticket,
        command=command,
        submitted_at=submitted_at.isoformat(),
        session_id=v2_session_id,
    )

    # LAUNCH_STARTED — v2 driver spawn 성공 = 사이클 진입 보장.
    spawn_elapsed_ms = int(
        (_now_utc() - submitted_at).total_seconds() * 1000
    )
    _emit_launch_event_safe(
        'LAUNCH_STARTED', ticket,
        session_id=v2_session_id,
        mode='v2',
        spawn_duration_ms=spawn_elapsed_ms,
        command=command,
    )

    # reader thread — driver 비정상 종료 시 LAUNCH_FAILED emit (회귀 검출).
    reader = threading.Thread(
        target=_v2_driver_reader_loop,
        args=(proc, ticket, command, submitted_at),
        name=f'v2-driver-reader-{ticket}',
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
        'session_id': v2_session_id,
    }


def _v2_driver_reader_loop(
    proc: subprocess.Popen,
    ticket: str,
    command: str,
    submitted_at: datetime,
) -> None:
    """v2 driver subprocess 종료 시 rc != 0 일 때만 LAUNCH_FAILED emit.

    v1 `_launch_reader_loop` (kanban.py) 와 다름:
      - LAUNCH_STARTED 발사 X (submit handler 가 Popen 직후 즉시 발사).
      - rc == 0 (정상 완료) 는 driver 자체 SSE (workflow.finish) 가 처리.
      - rc != 0 (crash) 만 LAUNCH_FAILED 발사 (회귀 검출).

    finally 블록에서 thread 핸들 set 자체 제거 (GC 누수 차단).
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
            return  # 정상 완료 — driver workflow.finish SSE 가 처리.

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
