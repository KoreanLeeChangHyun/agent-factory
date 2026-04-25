"""TerminalSSEChannel — terminal per-session SSE (링버퍼 제거, REST /workflow/history 경유)."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import threading
import time
import uuid
from collections.abc import Callable

from ._common import logger
from .event_filter import is_user_visible
from .sse_client_manager import _NDJSON_EVENT_MAP

# ---------------------------------------------------------------------------
# Workflow step detection patterns (stdout banner parsing)
# ---------------------------------------------------------------------------
_STEP_PATTERN = re.compile(
    r'(?:\[STEP\]\s+(PLAN|WORK|REPORT|DONE)'
    r'|║\s+\[●[^\]]*\]\s+(PLAN|WORK|REPORT|DONE))'
)
_INIT_PATTERN = re.compile(r'(?:\[INIT\]\s+|║\s+INIT:\s+)')
_PHASE_PATTERN = re.compile(
    r'(?:\[PHASE\]\s+(\d+)\s+(sequential|parallel)'
    r'|║\s+STATE:\s+Phase\s+(\d+)\s+(sequential|parallel))'
)
_FINISH_PATTERN = re.compile(
    r'(?:\[DONE\]\s+워크플로우\s+(완료|실패)'
    r'|║\s+DONE:\s+워크플로우\s+(완료|실패))'
)


def _parse_last_event_id(headers: object) -> int:
    """HTTP 요청 헤더에서 Last-Event-ID를 파싱한다.

    브라우저 EventSource는 재접속 시 자동으로 마지막 수신 이벤트의 id를
    Last-Event-ID 헤더에 담아 전송한다.

    Args:
        headers: HTTP 요청 헤더 객체

    Returns:
        파싱된 정수 ID. 헤더 없거나 파싱 실패 시 -1.
    """
    try:
        raw = headers.get('Last-Event-ID')
        if raw is None:
            return -1
        return int(str(raw).strip())
    except (ValueError, AttributeError):
        return -1


def _parse_last_event_id_from_query(path: str) -> int:
    """URL 쿼리 문자열에서 last_event_id 파라미터를 파싱한다.

    EventSource API는 사용자 정의 헤더 주입을 허용하지 않으므로,
    클라이언트가 재연결 시 이전 이벤트 ID를 헤더 대신 쿼리 파라미터로
    전달한다. 헤더 값(_parse_last_event_id)과 함께 사용하여 둘 중
    큰 쪽을 채택한다.

    Args:
        path: HTTP 요청 경로 (쿼리 포함, 예: ``/terminal/events?last_event_id=42``)

    Returns:
        파싱된 정수 ID. 파라미터 없거나 파싱 실패 시 -1.
    """
    try:
        if '?' not in path:
            return -1
        from urllib.parse import parse_qs
        qs = parse_qs(path.split('?', 1)[1])
        raw = qs.get('last_event_id', [None])[0]
        if raw is None:
            return -1
        return int(str(raw).strip())
    except (ValueError, TypeError, AttributeError):
        return -1


def _resolve_last_event_id(headers: object, path: str) -> int:
    """헤더와 쿼리 파라미터에서 last_event_id를 해석하여 최대값을 반환한다.

    EventSource는 새 인스턴스 생성 시 Last-Event-ID 헤더를 자동 포함하지 않으므로,
    명시적 쿼리 파라미터 경로가 주 경로다. 헤더 경로는 폴백이다.
    """
    return max(_parse_last_event_id(headers), _parse_last_event_id_from_query(path))


class TerminalSSEChannel:
    """터미널 출력 전용 SSE 브로드캐스트 채널.

    SSEClientManager와 동일한 인터페이스로 독립 인스턴스를 생성하여,
    기존 /events SSE와 간섭 없이 /terminal/events 전용 스트림을 제공한다.

    NDJSON 청크를 SSE 이벤트로 변환하여 연결된 모든 클라이언트에 전송한다.
    링버퍼(deque)는 제거되었으며, 재접속 시 과거 이벤트는 REST /workflow/history
    엔드포인트를 통해 jsonl 파일에서 복원한다.

    Attributes:
        _clients: 연결된 클라이언트의 wfile 객체 목록
        _lock: 클라이언트 목록 접근용 Lock
        _client_locks: wfile별 per-client Lock 딕셔너리
    """

    def __init__(self, persist_path: str | None = None) -> None:
        """초기화한다.

        Args:
            persist_path: 이벤트를 저장할 JSONL 파일 경로. None이면 persist 비활성.
        """
        self._clients: list = []
        self._lock: threading.Lock = threading.Lock()
        self._client_locks: dict = {}
        self._next_seq: int = 0
        self._persist_path: str | None = persist_path
        self._persist_lock: threading.Lock = threading.Lock()
        # stdout 기반 워크플로우 단계 감지
        self._step_buffer: str = ''
        self._current_step: str = ''
        self.on_step: Callable[[str, dict], None] | None = None

    def add(
        self,
        wfile: object,
        last_event_id: int = -1,
        skip_replay: bool = False,
    ) -> None:
        """클라이언트를 라이브 이벤트 스트림에 추가한다.

        링버퍼 재생 경로는 제거되었다. 과거 이벤트 복원은 REST /workflow/history
        엔드포인트를 통해 jsonl 파일에서 수행하며, 이 메서드는 신규 SSE 클라이언트를
        등록하여 이후 발행되는 라이브 이벤트만 수신하게 한다.

        ``skip_replay`` 파라미터는 하위호환을 위해 시그니처상 유지하나 동작에 영향 없음.
        ``last_event_id`` 파라미터 또한 유지하나 현재 미사용.

        Args:
            wfile: HTTP 핸들러의 wfile (소켓 출력 스트림)
            last_event_id: (미사용, 하위호환 유지)
            skip_replay: (미사용, 하위호환 유지)
        """
        with self._lock:
            self._clients.append(wfile)
            self._client_locks[id(wfile)] = threading.Lock()

    def remove(self, wfile: object) -> None:
        """클라이언트를 제거한다.

        Args:
            wfile: 제거할 클라이언트의 wfile
        """
        with self._lock:
            try:
                self._clients.remove(wfile)
            except ValueError:
                pass
            self._client_locks.pop(id(wfile), None)

    def get_lock(self, wfile: object) -> threading.Lock | None:
        """wfile에 대응하는 per-client lock을 반환한다.

        Args:
            wfile: lock을 획득할 클라이언트의 wfile

        Returns:
            해당 wfile의 Lock. 클라이언트가 존재하지 않으면 None.
        """
        with self._lock:
            return self._client_locks.get(id(wfile))

    def broadcast(self, data: dict) -> None:
        """NDJSON 메시지를 SSE 이벤트로 변환하여 모든 클라이언트에 전송한다.

        메시지 타입에 따라 적절한 SSE 이벤트 이름을 결정한다:
        - stream_event (text_delta) -> event: stdout
        - stream_event (input_json_delta) -> event: stdout
        - result -> event: result
        - system -> event: system
        - control_request -> event: permission
        - attachment (skill_listing) -> event: skill_listing
        - 기타 -> event: stdout (기본값)

        전송 실패한 클라이언트(연결 끊김)는 목록에서 제거한다.

        Args:
            data: 파싱된 NDJSON 메시지 dict
        """
        if not is_user_visible(data):
            return
        event_name = self._classify_event(data)
        payload = self._build_payload(data, event_name)
        json_payload = json.dumps(payload, ensure_ascii=False)

        self._emit_event(event_name, json_payload)

        # 파일 persist (서버 재시작 시 복원용) - 별도 락 사용
        if self._persist_path is not None:
            try:
                line = json.dumps(data, ensure_ascii=False) + '\n'
                with self._persist_lock:
                    with open(self._persist_path, 'a', encoding='utf-8') as f:
                        f.write(line)
            except (OSError, TypeError) as exc:
                logger.error("terminal_channel: broadcast persist 쓰기 실패 (%s): %s", self._persist_path, exc)

        # stdout 기반 워크플로우 단계 감지
        self._detect_step_from_broadcast(event_name, payload)

    def _emit_event(self, event_name: str, json_payload: str) -> None:
        """SSE 이벤트를 seq_id 부여 후 연결된 모든 클라이언트에 전송한다.

        링버퍼 저장 및 replay 버퍼링 로직은 제거되었다.
        """
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

    def _classify_event(self, data: dict) -> str:
        """NDJSON 메시지 타입으로부터 SSE 이벤트 이름을 결정한다.

        Args:
            data: 파싱된 NDJSON 메시지 dict

        Returns:
            SSE 이벤트 이름 문자열
        """
        msg_type = data.get('type', '')

        if msg_type == 'user_input':
            return 'user_input'

        if msg_type == 'stream_event':
            delta_type = (
                data.get('event', {}).get('delta', {}).get('type', '')
            )
            return _NDJSON_EVENT_MAP.get(delta_type, 'stdout')

        if msg_type == 'assistant':
            return 'stdout'

        if msg_type == 'attachment':
            attachment_type = data.get('attachment', {}).get('type', '')
            if attachment_type == 'skill_listing':
                return 'skill_listing'
            return 'stdout'

        return _NDJSON_EVENT_MAP.get(msg_type, 'stdout')

    def _build_payload(self, data: dict, event_name: str) -> dict:
        """SSE 클라이언트에 보낼 페이로드를 구성한다.

        Args:
            data: 원본 NDJSON 메시지 dict
            event_name: 결정된 SSE 이벤트 이름

        Returns:
            페이로드 dict
        """
        if event_name == 'user_input':
            return {'text': data.get('text', '')}
        if event_name == 'skill_listing':
            return self._build_skill_listing_payload(data)
        if event_name == 'stdout':
            return self._build_stdout_payload(data)
        if event_name == 'result':
            return self._build_result_payload(data)
        if event_name == 'system':
            return self._build_system_payload(data)
        if event_name == 'permission':
            req = data.get('request', {})
            return {
                'kind': 'permission',
                'request_id': data.get('request_id', ''),
                'tool_name': req.get('tool_name', ''),
                'description': req.get('description', ''),
                'input': req.get('input', {}),
                'raw': data,
            }
        if event_name == 'rate_limit':
            info = data.get('rate_limit_info', {}) or {}
            return {
                'kind': 'rate_limit',
                'status': info.get('status', 'unknown'),
                'resets_at': info.get('resetsAt'),
                'rate_limit_type': info.get('rateLimitType', ''),
                'is_using_overage': bool(info.get('isUsingOverage', False)),
                'overage_status': info.get('overageStatus', ''),
                'session_id': data.get('session_id', ''),
            }
        if event_name == 'error':
            return {
                'kind': 'error',
                'message': data.get('message', 'Unknown error'),
                'exit_code': data.get('exit_code'),
                'session_id': data.get('session_id', ''),
            }
        # 기본: raw 데이터 전달
        return {'kind': data.get('type', 'unknown'), 'raw': data}

    def _build_skill_listing_payload(self, data: dict) -> dict:
        """skill_listing 이벤트 페이로드를 구성한다.

        Args:
            data: 원본 NDJSON 메시지 dict (type == 'attachment')

        Returns:
            skill_listing 페이로드 dict
        """
        attachment = data.get('attachment', {})
        return {
            'kind': 'skill_listing',
            'content': attachment.get('content', ''),
            'skillCount': attachment.get('skillCount', 0),
            'isInitial': attachment.get('isInitial', False),
        }

    def _build_stdout_payload(self, data: dict) -> dict:
        """stdout 이벤트 페이로드를 구성한다.

        stream_event의 text_delta에서 텍스트 청크를 추출하거나,
        assistant 메시지에서 전체 텍스트를 추출한다.

        Args:
            data: 원본 NDJSON 메시지 dict

        Returns:
            stdout 페이로드 dict
        """
        msg_type = data.get('type', '')

        if msg_type == 'stream_event':
            event = data.get('event', {})
            delta = event.get('delta', {})
            delta_type = delta.get('type', '')

            if delta_type == 'text_delta':
                return {
                    'kind': 'text_delta',
                    'chunk': delta.get('text', ''),
                }
            if delta_type == 'input_json_delta':
                return {
                    'kind': 'input_json_delta',
                    'chunk': delta.get('partial_json', ''),
                }
            # content_block_start, message_start, message_delta 등 기타 stream_event
            payload = {
                'kind': event.get('type', 'stream_event'),
                'raw': event,
            }
            # usage 위치는 이벤트 타입마다 다르다:
            #   - message_start: event.message.usage (input_tokens + cache_* + output_tokens=1)
            #   - message_delta: event.usage (output_tokens 만, input 없음)
            # input 이 없는 이벤트(message_delta)에 0 을 넣어 보내면 클라의
            # setInputTokens(0) 이 바를 0% 로 깜빡이게 한다. 실제 있는 필드만 전파한다.
            event_usage = event.get('usage') or event.get('message', {}).get('usage')
            if event_usage:
                payload_usage: dict = {}
                has_input = any(
                    k in event_usage
                    for k in ('input_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens')
                )
                if has_input:
                    payload_usage['input_tokens'] = (
                        event_usage.get('input_tokens', 0)
                        + event_usage.get('cache_read_input_tokens', 0)
                        + event_usage.get('cache_creation_input_tokens', 0)
                    )
                if 'output_tokens' in event_usage:
                    payload_usage['output_tokens'] = event_usage['output_tokens']
                if payload_usage:
                    payload['usage'] = payload_usage
            return payload

        if msg_type == 'assistant':
            content = data.get('message', {}).get('content', [])
            text_parts = [
                block.get('text', '')
                for block in content
                if block.get('type') == 'text'
            ]
            payload = {
                'kind': 'assistant',
                'text': ''.join(text_parts),
            }
            usage = data.get('message', {}).get('usage', {})
            if usage:
                payload['usage'] = {
                    'input_tokens': (usage.get('input_tokens', 0)
                        + usage.get('cache_read_input_tokens', 0)
                        + usage.get('cache_creation_input_tokens', 0)),
                    'output_tokens': usage.get('output_tokens', 0),
                }
            return payload

        return {'kind': msg_type or 'unknown', 'raw': data}

    def _build_result_payload(self, data: dict) -> dict:
        """result 이벤트 페이로드를 구성한다.

        Args:
            data: 원본 NDJSON 메시지 dict

        Returns:
            result 페이로드 dict
        """
        usage = data.get('usage', {})
        return {
            'kind': 'result',
            'done': True,
            'subtype': data.get('subtype', ''),
            'is_error': data.get('is_error', False),
            'result': data.get('result', ''),
            'duration_ms': data.get('duration_ms', 0),
            'session_id': data.get('session_id', ''),
            'cost_usd': data.get('total_cost_usd', 0),
            'input_tokens': usage.get('input_tokens', 0)
                + usage.get('cache_read_input_tokens', 0)
                + usage.get('cache_creation_input_tokens', 0),
            'output_tokens': usage.get('output_tokens', 0),
        }

    # subtype 별 클라이언트가 top-level 로 접근하는 필드 계약.
    # 신규 subtype 추가 시 이 표에 명시하지 않으면 클라이언트에서 raw 경유로 접근해야 한다.
    _SYSTEM_TOP_LEVEL_FIELDS: dict[str, tuple[str, ...]] = {
        'task_started': ('task_id', 'tool_use_id', 'description', 'last_tool_name'),
        'task_progress': ('task_id', 'tool_use_id', 'description', 'last_tool_name'),
        'task_notification': ('task_id', 'tool_use_id', 'status', 'summary'),
        'process_exit': ('exit_code',),
    }

    def _build_system_payload(self, data: dict) -> dict:
        """system 이벤트 페이로드를 구성한다.

        subtype 에 따라 클라이언트가 top-level 로 접근하는 필드를
        ``_SYSTEM_TOP_LEVEL_FIELDS`` 계약에 따라 추출하여 노출한다.
        클라이언트는 raw 경유 폴백 없이 단순 접근만 수행할 수 있다.

        Args:
            data: 원본 NDJSON 메시지 dict

        Returns:
            system 페이로드 dict
        """
        subtype = data.get('subtype', '')
        payload: dict = {
            'kind': 'system',
            'subtype': subtype,
            'session_id': data.get('session_id', ''),
            'raw': data,
        }
        for key in self._SYSTEM_TOP_LEVEL_FIELDS.get(subtype, ()):
            if key in data:
                payload[key] = data[key]
        return payload

    @property
    def client_count(self) -> int:
        """현재 연결된 클라이언트 수를 반환한다."""
        with self._lock:
            return len(self._clients)

    @property
    def current_step(self) -> str:
        """현재 워크플로우 단계를 반환한다."""
        return self._current_step

    # ------------------------------------------------------------------
    # Phase 1: workflow_step SSE event
    # ------------------------------------------------------------------

    def emit_step(self, step_name: str, detail: dict | None = None) -> None:
        """workflow_step SSE 이벤트를 발행하고 jsonl 파일에 기록한다.

        broadcast()를 거치지 않으므로 jsonl 기록을 직접 수행한다.

        Args:
            step_name: 단계 이름 (init, plan, work, report, done)
            detail: 추가 정보 dict (phase, mode, trigger 등)
        """
        prev = self._current_step
        self._current_step = step_name
        payload: dict = {'step': step_name, 'prev_step': prev}
        if detail:
            payload.update(detail)
        self._emit_event('workflow_step', json.dumps(payload, ensure_ascii=False))

        # jsonl 기록 (broadcast 미경유이므로 직접 persist)
        if self._persist_path is not None:
            try:
                record = {'type': 'workflow_step', 'step': step_name, 'prev_step': prev}
                if detail:
                    record.update(detail)
                line = json.dumps(record, ensure_ascii=False) + '\n'
                with self._persist_lock:
                    with open(self._persist_path, 'a', encoding='utf-8') as f:
                        f.write(line)
            except (OSError, TypeError) as exc:
                logger.error("terminal_channel: emit_step persist 쓰기 실패 (%s): %s", self._persist_path, exc)

        if self.on_step:
            try:
                self.on_step(step_name, payload)
            except Exception:
                pass

    def _detect_step_from_broadcast(self, event_name: str, payload: dict) -> None:
        """broadcast 된 stdout 이벤트에서 워크플로우 단계 전이를 감지한다."""
        if event_name != 'stdout':
            return
        kind = payload.get('kind', '')
        if kind == 'text_delta':
            self._step_buffer += payload.get('chunk', '')
        elif kind == 'assistant':
            self._step_buffer += payload.get('text', '')
        else:
            return
        # 개행 단위로 라인을 소비하여 패턴 매칭
        while '\n' in self._step_buffer:
            line, self._step_buffer = self._step_buffer.split('\n', 1)
            self._check_step_line(line.strip())

    def _check_step_line(self, line: str) -> None:
        """단일 stdout 라인에서 워크플로우 단계 패턴을 검사한다."""
        if not line:
            return
        m = _STEP_PATTERN.search(line)
        if m:
            step = (m.group(1) or m.group(2)).lower()
            self.emit_step(step, {'trigger': 'stdout'})
            return
        m = _INIT_PATTERN.search(line)
        if m:
            self.emit_step('init', {'trigger': 'stdout'})
            return
        m = _PHASE_PATTERN.search(line)
        if m:
            phase_num = int(m.group(1) or m.group(3))
            mode = m.group(2) or m.group(4)
            self.emit_step(self._current_step, {
                'trigger': 'stdout',
                'phase': phase_num,
                'mode': mode,
            })
            return
        m = _FINISH_PATTERN.search(line)
        if m:
            result = 'success' if (m.group(1) or m.group(2)) == '완료' else 'failure'
            self.emit_step('done', {'trigger': 'stdout', 'result': result})


# ---------------------------------------------------------------------------
# Image Validation Helper
# ---------------------------------------------------------------------------

_ALLOWED_MEDIA_TYPES = {'image/png', 'image/jpeg', 'image/gif', 'image/webp'}
