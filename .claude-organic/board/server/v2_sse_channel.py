"""V2WorkflowSSEChannel — per-session NDJSON broadcast + jsonl persist.

v1 TerminalSSEChannel 과 분리된 v2 driver 전용 SSE 채널.
한 V2WorkflowSession 당 하나의 채널 인스턴스가 할당된다.

driver 가 의미별 endpoint (`/step`, `/stdout`, `/phase`, `/finish`) 를 호출하므로
broadcast 자체는 단순 forward — 의미 분류 (text_delta / tool_use 등) 는
프론트엔드 측 분기로 위임한다.
"""

from __future__ import annotations

import json
import threading
import time

from ._common import logger


class V2WorkflowSSEChannel:
    """v2 driver 전용 SSE 채널 — per-session client fan-out.

    Attributes:
        session_id: 소유 세션 ID (wf-T-NNN-<uuid>)
        _clients: 연결된 SSE 클라이언트 wfile 목록
        _lock: 클라이언트 목록 접근 Lock
        _client_locks: wfile 별 per-client Lock
        _next_seq: SSE id 시퀀스
        _persist_path: NDJSON 파일 경로 (None 이면 persist 비활성)
        _persist_lock: 파일 write Lock
    """

    def __init__(self, session_id: str, persist_path: str | None = None) -> None:
        """초기화한다.

        Args:
            session_id: 소유 세션 ID
            persist_path: NDJSON 파일 경로 (None 이면 persist 비활성)
        """
        self.session_id: str = session_id
        self._clients: list = []
        self._lock: threading.Lock = threading.Lock()
        self._client_locks: dict = {}
        self._next_seq: int = 0
        self._persist_path: str | None = persist_path
        self._persist_lock: threading.Lock = threading.Lock()

    @property
    def persist_path(self) -> str | None:
        """NDJSON persist 파일 절대 경로 (persist 비활성 시 None).

        T-513 P1 — `GET /api/v2/sessions/<id>/history` endpoint 가 본 경로를
        read 하여 과거 이벤트를 일괄 반환한다 (REST 단일 출처 정책 정합).
        """
        return self._persist_path

    def add(self, wfile: object) -> None:
        """SSE 클라이언트를 라이브 스트림에 등록한다.

        replay 는 별도 endpoint (GET /api/v2/sessions/<id>/history) 가 NDJSON
        파일에서 read. 본 메서드는 신규 클라이언트만 등록하여 이후 라이브
        이벤트 수신.
        """
        with self._lock:
            self._clients.append(wfile)
            self._client_locks[id(wfile)] = threading.Lock()

    def remove(self, wfile: object) -> None:
        """클라이언트를 제거한다."""
        with self._lock:
            try:
                self._clients.remove(wfile)
            except ValueError:
                pass
            self._client_locks.pop(id(wfile), None)

    def get_lock(self, wfile: object) -> threading.Lock | None:
        """wfile per-client lock 을 반환한다."""
        with self._lock:
            return self._client_locks.get(id(wfile))

    def client_count(self) -> int:
        """현재 연결된 클라이언트 수를 반환한다 (테스트용)."""
        with self._lock:
            return len(self._clients)

    def broadcast(self, event_name: str, payload: dict) -> None:
        """SSE 이벤트를 전송 + NDJSON 파일 persist 한다.

        Args:
            event_name: SSE event 이름 (예: workflow_step, workflow_stdout)
            payload: 이벤트 페이로드 dict (JSON 직렬화 가능)
        """
        json_payload = json.dumps(payload, ensure_ascii=False)
        self._emit_event(event_name, json_payload)

        if self._persist_path is not None:
            try:
                line = json.dumps(
                    {
                        'ts': time.time(),
                        'event': event_name,
                        'payload': payload,
                    },
                    ensure_ascii=False,
                ) + '\n'
                with self._persist_lock:
                    with open(self._persist_path, 'a', encoding='utf-8') as f:
                        f.write(line)
            except (OSError, TypeError) as exc:
                logger.error(
                    "v2_sse_channel[%s]: persist 쓰기 실패 (%s): %s",
                    self.session_id, self._persist_path, exc,
                )

    def emit_step(
        self, step: str, phase: str = '', prev_step: str = '',
        extras: dict | None = None,
    ) -> None:
        """workflow_step 이벤트 발화 — Step 전이.

        Args:
            step: 새 Step (NONE/INIT/PLAN/WORK/VALIDATE/REPORT/DONE/FAILED)
            phase: WORK 내부 sub-phase (P1, P2, ...). 없으면 빈 문자열
            prev_step: 직전 Step (frontend FSM 검증용)
            extras: T-495 P3 — verdict/commit/retry 등 forward-compatible 메타.
                fixed key (session_id/step/phase/prev_step) 는 보호됨.
        """
        payload = {
            'session_id': self.session_id,
            'step': step,
            'phase': phase,
            'prev_step': prev_step,
        }
        if extras:
            for k, v in extras.items():
                if k not in payload:
                    payload[k] = v
        self.broadcast('workflow_step', payload)

    def emit_stdout(self, text: str, raw: dict | None = None) -> None:
        """workflow_stdout 이벤트 발화 — claude -p stdout NDJSON chunk.

        Args:
            text: 텍스트 chunk (frontend 빠른 path)
            raw: 원본 NDJSON dict (frontend 분기 렌더 필요 시)
        """
        payload = {
            'session_id': self.session_id,
            'text': text,
        }
        if raw is not None:
            payload['raw'] = raw
        self.broadcast('workflow_stdout', payload)

    def emit_phase(
        self, phase: str, action: str = 'start',
        extras: dict | None = None,
    ) -> None:
        """workflow_phase 이벤트 발화 — WORK 내부 phase 전이.

        Args:
            phase: P1, P2, ...
            action: start | end
            extras: T-495 P3 — verdict/commit/retry 등 forward-compatible 메타.
        """
        payload = {
            'session_id': self.session_id,
            'phase': phase,
            'action': action,
        }
        if extras:
            for k, v in extras.items():
                if k not in payload:
                    payload[k] = v
        self.broadcast('workflow_phase', payload)

    def emit_finish(
        self, outcome: str, summary: str = '',
        extras: dict | None = None,
    ) -> None:
        """workflow_finish 이벤트 발화 — 사이클 종결.

        Args:
            outcome: ok | fail
            summary: 종결 사유 / 한 줄 요약
            extras: T-495 P3 — verdict/commit/retry 등 forward-compatible 메타.
        """
        payload = {
            'session_id': self.session_id,
            'outcome': outcome,
            'summary': summary,
        }
        if extras:
            for k, v in extras.items():
                if k not in payload:
                    payload[k] = v
        self.broadcast('workflow_finish', payload)

    def _emit_event(self, event_name: str, json_payload: str) -> None:
        """SSE 이벤트를 seq_id 부여 후 모든 클라이언트에 전송한다."""
        dead_clients: list = []
        with self._lock:
            seq_id = self._next_seq
            self._next_seq += 1
            message = f"id: {seq_id}\nevent: {event_name}\ndata: {json_payload}\n\n"
            encoded = message.encode('utf-8')
            clients_snapshot = list(self._clients)

        for wfile in clients_snapshot:
            wfile_id = id(wfile)
            client_lock = self._client_locks.get(wfile_id)
            if client_lock is None:
                continue
            try:
                with client_lock:
                    wfile.write(encoded)
                    wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                dead_clients.append(wfile)

        if dead_clients:
            with self._lock:
                for wfile in dead_clients:
                    try:
                        self._clients.remove(wfile)
                    except ValueError:
                        pass
                    self._client_locks.pop(id(wfile), None)
