#!/usr/bin/env -S python3 -u
"""Board HTTP server with SSE real-time updates.

ThreadingHTTPServer 기반 커스텀 서버로, 정적 파일 서빙과 /events SSE 엔드포인트를
동시 제공한다. FileWatcher가 감시 대상 디렉터리의 변경을 감지하여 SSE로 푸시한다.

감시 대상:
    .claude.workflow/kanban/active/, .claude.workflow/kanban/done/ -> kanban 이벤트
    .claude.workflow/workflow/, .claude.workflow/workflow/.history/ -> workflow 이벤트
    .claude.workflow/dashboard/ -> dashboard 이벤트
"""

from __future__ import annotations

import atexit
import collections
import datetime
import hashlib
import json
import logging
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from board_data import (
    KANBAN_DIRS_LIST,
    WF_BASE,
    WF_HISTORY,
    DASH_BASE,
    DASH_FILES,
    WF_ENTRY_RE,
    WF_DETAIL_FILES,
    _resolve_settings_file,
    _parse_env_file,
    _update_env_value,
    _read_kanban_tickets,
    _read_dashboard,
    _list_workflow_entries,
    _get_git_branch,
    _workflow_detail,
    _resolve_memory_dir,
    _list_memory_files,
    _read_memory_file,
    _write_memory_file,
    _delete_memory_file,
    _list_rules_files,
    _read_rules_file,
    _write_rules_file,
    _delete_rules_file,
    _list_prompt_files,
    _read_prompt_file,
    _write_prompt_file,
    _delete_prompt_file,
    _read_claude_md,
    _write_claude_md,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PORT_RANGE_START: int = 9900
PORT_RANGE_END: int = 9999
WATCH_INTERVAL: float = 1.0
SERVER_STARTED_AT: str = time.strftime('%Y-%m-%d %H:%M:%S')
SERVER_PID: int = os.getpid()

# 감시 대상 경로 -> SSE 이벤트 타입 매핑
WATCH_DIRS: dict[str, str] = {
    os.path.join('.claude.workflow', 'kanban', 'open'): 'kanban',
    os.path.join('.claude.workflow', 'kanban', 'progress'): 'kanban',
    os.path.join('.claude.workflow', 'kanban', 'review'): 'kanban',
    os.path.join('.claude.workflow', 'kanban', 'done'): 'kanban',
    os.path.join('.claude.workflow', 'workflow'): 'workflow',
    os.path.join('.claude.workflow', 'workflow', '.history'): 'workflow',
    os.path.join('.claude.workflow', 'dashboard'): 'dashboard',
}

# Workflow sync (init-claude-workflow.sh) 부트스트랩 URL과 동시 실행 차단 락
_WORKFLOW_SYNC_URL: str = (
    'https://raw.githubusercontent.com/KoreanLeeChangHyun/'
    'claude-workflow/main/init-claude-workflow.sh'
)
_workflow_sync_lock: threading.Lock = threading.Lock()


# ---------------------------------------------------------------------------
# Dynamic Port Allocation
# ---------------------------------------------------------------------------

def resolve_port(project_root: str) -> int:
    """프로젝트 경로 기반으로 9900~9999 범위에서 사용 가능한 포트를 반환한다.

    프로젝트 경로를 MD5 해싱하여 초기 포트를 결정하고, 충돌 시 순차 탐색한다.

    Args:
        project_root: 프로젝트 루트 절대 경로

    Returns:
        사용 가능한 포트 번호 (9900~9999 범위)

    Raises:
        RuntimeError: 9900~9999 범위의 포트가 모두 사용 중인 경우
    """
    range_size = PORT_RANGE_END - PORT_RANGE_START + 1
    hash_bytes = hashlib.md5(project_root.encode()).digest()
    hash_int = int.from_bytes(hash_bytes[:4], byteorder='big')
    start_offset = hash_int % range_size

    for i in range(range_size):
        port = PORT_RANGE_START + (start_offset + i) % range_size
        if not is_port_in_use(port):
            return port

    raise RuntimeError(
        f"포트 {PORT_RANGE_START}~{PORT_RANGE_END} 범위의 모든 포트가 사용 중입니다."
    )


# ---------------------------------------------------------------------------
# FileWatcher
# ---------------------------------------------------------------------------

class FileWatcher:
    """파일 시스템 변경 감시기.

    os.scandir() 기반으로 감시 대상 디렉터리의 엔트리 mtime을 추적하고,
    변경 감지 시 콜백을 호출한다.

    Attributes:
        _project_root: 프로젝트 루트 절대 경로
        _snapshots: 디렉터리별 {파일경로: mtime} 스냅샷
        _on_change: 변경 감지 시 호출할 콜백 Callable[[str, list[str]], None]
        _running: 감시 루프 실행 플래그
    """

    def __init__(
        self,
        project_root: str,
        on_change: Callable[[str, list[str]], None],
    ) -> None:
        """초기화한다.

        Args:
            project_root: 프로젝트 루트 절대 경로
            on_change: 변경 감지 시 호출할 콜백, event_type(str)과 변경 파일명 목록(list[str])을 인자로 받음
        """
        self._project_root: str = project_root
        self._snapshots: dict[str, dict[str, float]] = {}
        self._on_change: Callable[[str, list[str]], None] = on_change
        self._running: bool = False
        self._build_initial_snapshots()

    def _build_initial_snapshots(self) -> None:
        """모든 감시 대상 디렉터리의 초기 스냅샷을 구성한다."""
        for rel_dir in WATCH_DIRS:
            abs_dir = os.path.join(self._project_root, rel_dir)
            self._snapshots[rel_dir] = self._scan_dir(abs_dir)

    def _scan_dir(self, abs_dir: str) -> dict[str, float]:
        """디렉터리를 스캔하여 {엔트리경로: mtime} dict를 반환한다.

        Args:
            abs_dir: 스캔할 디렉터리의 절대 경로

        Returns:
            엔트리 경로를 키, mtime을 값으로 하는 dict.
            디렉터리가 존재하지 않으면 빈 dict.
        """
        result: dict[str, float] = {}
        if not os.path.isdir(abs_dir):
            return result
        try:
            # 디렉터리 자체의 mtime도 추적 (파일 추가/삭제 감지)
            result['__dir__'] = os.stat(abs_dir).st_mtime
            with os.scandir(abs_dir) as entries:
                for entry in entries:
                    try:
                        result[entry.path] = entry.stat().st_mtime
                    except OSError:
                        # 파일이 스캔 중 삭제된 경우
                        pass
        except OSError:
            pass
        return result

    def run(self) -> None:
        """감시 루프를 실행한다. daemon 스레드에서 호출된다."""
        self._running = True
        while self._running:
            time.sleep(WATCH_INTERVAL)
            self._check_changes()

    def stop(self) -> None:
        """감시 루프를 중지한다."""
        self._running = False

    def _check_changes(self) -> None:
        """모든 감시 대상의 변경 여부를 확인하고 콜백을 호출한다."""
        changed_files: dict[str, list[str]] = {}
        for rel_dir, event_type in WATCH_DIRS.items():
            abs_dir = os.path.join(self._project_root, rel_dir)
            old_snapshot = self._snapshots[rel_dir]
            new_snapshot = self._scan_dir(abs_dir)
            if new_snapshot != old_snapshot:
                self._snapshots[rel_dir] = new_snapshot
                # 변경된 파일명 수집 (__dir__ 제외)
                old_paths = {p for p in old_snapshot if p != '__dir__'}
                new_paths = {p for p in new_snapshot if p != '__dir__'}
                modified = {
                    p for p in old_paths & new_paths
                    if old_snapshot[p] != new_snapshot[p]
                }
                added = new_paths - old_paths
                removed = old_paths - new_paths
                file_names = [
                    os.path.basename(p)
                    for p in modified | added | removed
                ]
                if event_type not in changed_files:
                    changed_files[event_type] = []
                changed_files[event_type].extend(file_names)

        for event_type, files in changed_files.items():
            self._on_change(event_type, files)


# ---------------------------------------------------------------------------
# SSE Client Manager
# ---------------------------------------------------------------------------

class SSEClientManager:
    """SSE 클라이언트 연결 관리자.

    연결된 클라이언트 목록을 thread-safe하게 관리하고,
    이벤트를 모든 클라이언트에 브로드캐스트한다.

    Attributes:
        _clients: 연결된 클라이언트의 wfile 객체 목록
        _lock: 클라이언트 목록 접근용 Lock
        _client_locks: wfile별 per-client Lock 딕셔너리
    """

    def __init__(self) -> None:
        """초기화한다."""
        self._clients: list = []
        self._lock: threading.Lock = threading.Lock()
        self._client_locks: dict = {}

    def add(self, wfile: object) -> None:
        """클라이언트를 추가한다.

        Args:
            wfile: HTTP 핸들러의 wfile (소켓 출력 스트림)
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

    def broadcast(self, event_type: str, files: list | None = None) -> None:
        """모든 클라이언트에 SSE 이벤트를 전송한다.

        전송 실패한 클라이언트(연결 끊김)는 목록에서 제거한다.
        per-client lock으로 heartbeat 루프와의 concurrent write를 방지한다.

        Args:
            event_type: SSE 이벤트 타입 (kanban, workflow, dashboard)
            files: 변경된 파일 목록. kanban 이벤트 시 data 필드에 JSON으로 포함됨.
                   None이면 타임스탬프 문자열을 data로 전송.
        """
        if files is not None:
            data = json.dumps({"files": files})
        else:
            data = str(int(time.time()))
        message = f"event: {event_type}\ndata: {data}\n\n"
        encoded = message.encode('utf-8')

        dead_clients: list = []
        with self._lock:
            clients_snapshot = list(self._clients)

        for wfile in clients_snapshot:
            client_lock = self._client_locks.get(id(wfile))
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


# ---------------------------------------------------------------------------
# Terminal SSE Channel
# ---------------------------------------------------------------------------

# NDJSON 메시지 타입 -> SSE 이벤트 이름 매핑
_NDJSON_EVENT_MAP: dict[str, str] = {
    'text_delta': 'stdout',
    'input_json_delta': 'stdout',
    'result': 'result',
    'system': 'system',
    'control_request': 'permission',
    'error': 'error',
    'user_input': 'user_input',
    'attachment': 'skill_listing',
}


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

    Attributes:
        _clients: 연결된 클라이언트의 wfile 객체 목록
        _lock: 클라이언트 목록 접근용 Lock
        _client_locks: wfile별 per-client Lock 딕셔너리
        _history: 최근 SSE 이벤트 링 버퍼 (재접속 시 재생용)
    """

    def __init__(self, history_size: int = 1000, persist_path: str | None = None) -> None:
        """초기화한다.

        Args:
            history_size: 링 버퍼에 보관할 최근 이벤트 개수. 0이면 버퍼 비활성.
            persist_path: 이벤트를 저장할 JSONL 파일 경로. None이면 persist 비활성.
        """
        self._clients: list = []
        self._lock: threading.Lock = threading.Lock()
        self._client_locks: dict = {}
        # 이벤트를 (seq_id, encoded) 튜플로 저장해 Last-Event-ID 기반 재개 지원
        self._history: collections.deque = collections.deque(maxlen=history_size)
        self._next_seq: int = 0
        self._persist_path: str | None = persist_path
        self._persist_lock: threading.Lock = threading.Lock()

    def add(self, wfile: object, last_event_id: int = -1) -> None:
        """클라이언트를 추가하고, last_event_id 이후의 히스토리를 재생한다.

        Args:
            wfile: HTTP 핸들러의 wfile (소켓 출력 스트림)
            last_event_id: 클라이언트가 마지막으로 수신한 이벤트 seq_id (-1=전체 재생)
        """
        with self._lock:
            self._clients.append(wfile)
            client_lock = threading.Lock()
            self._client_locks[id(wfile)] = client_lock
            with client_lock:
                for seq_id, encoded in list(self._history):
                    if seq_id <= last_event_id:
                        continue  # 이미 수신한 이벤트는 건너뜀
                    try:
                        wfile.write(encoded)
                        wfile.flush()
                    except (BrokenPipeError, ConnectionResetError, OSError):
                        break

    def clear_history(self) -> None:
        """히스토리 버퍼를 비운다. 새 세션 시작 시 이전 이벤트를 제거하기 위함."""
        with self._lock:
            self._history.clear()
            self._next_seq = 0

    def replay_from_history(self, data: dict) -> None:
        """이전에 저장된 이벤트를 히스토리 버퍼에만 복원한다.

        서버 재시작 후 persist 파일에서 이벤트를 로드할 때 사용한다.
        클라이언트 브로드캐스트와 파일 쓰기는 수행하지 않는다.

        Args:
            data: 파싱된 NDJSON 메시지 dict
        """
        event_name = self._classify_event(data)
        payload = self._build_payload(data, event_name)
        json_payload = json.dumps(payload, ensure_ascii=False)
        seq_id = self._next_seq
        self._next_seq += 1
        message = f"id: {seq_id}\nevent: {event_name}\ndata: {json_payload}\n\n"
        self._history.append((seq_id, message.encode('utf-8')))

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
        event_name = self._classify_event(data)
        payload = self._build_payload(data, event_name)
        json_payload = json.dumps(payload, ensure_ascii=False)

        dead_clients: list = []
        with self._lock:
            seq_id = self._next_seq
            self._next_seq += 1
            # SSE `id:` 필드 → 브라우저가 자동으로 Last-Event-ID 재송신
            message = f"id: {seq_id}\nevent: {event_name}\ndata: {json_payload}\n\n"
            encoded = message.encode('utf-8')
            # 링 버퍼에 (seq_id, encoded) 튜플로 저장
            self._history.append((seq_id, encoded))
            clients_snapshot = list(self._clients)

        for wfile in clients_snapshot:
            client_lock = self._client_locks.get(id(wfile))
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

        # 파일 persist (서버 재시작 시 복원용) - 별도 락 사용
        if self._persist_path is not None:
            try:
                line = json.dumps(data, ensure_ascii=False) + '\n'
                with self._persist_lock:
                    with open(self._persist_path, 'a', encoding='utf-8') as f:
                        f.write(line)
            except (OSError, TypeError):
                pass  # persist 실패는 세션 동작을 막지 않는다

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
            if 'usage' in event:
                event_usage = event['usage']
                payload['usage'] = {
                    'input_tokens': (event_usage.get('input_tokens', 0)
                        + event_usage.get('cache_read_input_tokens', 0)
                        + event_usage.get('cache_creation_input_tokens', 0)),
                    'output_tokens': event_usage.get('output_tokens', 0),
                }
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

    def _build_system_payload(self, data: dict) -> dict:
        """system 이벤트 페이로드를 구성한다.

        Args:
            data: 원본 NDJSON 메시지 dict

        Returns:
            system 페이로드 dict
        """
        return {
            'kind': 'system',
            'subtype': data.get('subtype', ''),
            'session_id': data.get('session_id', ''),
            'raw': data,
        }

    @property
    def client_count(self) -> int:
        """현재 연결된 클라이언트 수를 반환한다."""
        with self._lock:
            return len(self._clients)


# ---------------------------------------------------------------------------
# Image Validation Helper
# ---------------------------------------------------------------------------

_ALLOWED_MEDIA_TYPES = {'image/png', 'image/jpeg', 'image/gif', 'image/webp'}


def _validate_images(images: list) -> str | None:
    """이미지 목록의 유효성을 검증한다.

    각 항목에 data(문자열)와 허용된 media_type이 존재하는지 확인한다.

    Args:
        images: 검증할 이미지 항목 목록.

    Returns:
        유효하지 않을 때 에러 메시지 문자열, 유효하면 None.
    """
    if not isinstance(images, list):
        return 'Invalid "images" field: must be a list'

    for i, img in enumerate(images):
        if not isinstance(img, dict):
            return f'Invalid image at index {i}: must be an object'

        data = img.get('data')
        if not isinstance(data, str) or not data:
            return f'Invalid image at index {i}: missing or invalid "data" field'

        media_type = img.get('media_type')
        if media_type not in _ALLOWED_MEDIA_TYPES:
            allowed = ', '.join(sorted(_ALLOWED_MEDIA_TYPES))
            return (
                f'Invalid image at index {i}: '
                f'"media_type" must be one of [{allowed}], got "{media_type}"'
            )

    return None


# ---------------------------------------------------------------------------
# Claude Process Manager
# ---------------------------------------------------------------------------

class ClaudeProcess:
    """Claude CLI 프로세스 생명주기 관리자.

    subprocess.Popen으로 Claude CLI를 실행하고, stdin/stdout을 통한
    NDJSON 양방향 통신을 관리한다.

    Attributes:
        _process: subprocess.Popen 인스턴스 (프로세스 시작 전에는 None)
        _session_id: system/init 메시지에서 추출한 세션 ID
        _status: 프로세스 상태 (stopped/running/idle)
        _stdin_lock: stdin 접근 보호 Lock
        _stdout_thread: stdout 읽기 데몬 스레드
        _channel: SSE 브로드캐스트 채널
    """

    def __init__(self, channel: TerminalSSEChannel, persist_file: str | None = None) -> None:
        """초기화한다.

        Args:
            channel: NDJSON 이벤트를 브로드캐스트할 TerminalSSEChannel 인스턴스
            persist_file: session_id를 영속화할 파일 경로 (선택적)
        """
        self._process: subprocess.Popen | None = None
        self._session_id: str = ''
        self._model: str = ''
        self._permission_mode: str = ''
        self._status: str = 'stopped'
        self._stdin_lock: threading.Lock = threading.Lock()
        self._stdout_thread: threading.Thread | None = None
        self._channel: TerminalSSEChannel = channel
        self._init_event: threading.Event = threading.Event()
        self._persist_file: str | None = persist_file

    def spawn(
        self,
        extra_args: list[str] | None = None,
        env_extras: dict[str, str] | None = None,
    ) -> dict:
        """Claude CLI 프로세스를 시작한다.

        이미 실행 중인 프로세스가 있으면 먼저 종료한다.
        프로세스 시작 후 system/init SSE 이벤트를 최대 10초까지 대기하여
        session_id를 응답에 포함한다.

        Args:
            extra_args: 추가 CLI 인자 목록 (선택적)
            env_extras: 자식 프로세스에 주입할 추가 환경변수 dict (선택적).
                        예: {"_WF_SESSION_TYPE": "workflow", "_WF_TICKET_ID": "T-238"}

        Returns:
            시작 결과 dict: {"ok": True/False, "session_id": str, "error": str}
        """
        if self._process and self._process.poll() is None:
            self.kill()
            self._init_event.clear()

        # 이전 stdout 스레드가 완전히 종료될 때까지 대기
        if self._stdout_thread and self._stdout_thread.is_alive():
            self._stdout_thread.join(timeout=3)

        # -p(print mode)로 시작: --input-format stream-json은 print mode 전용
        # 이미지 content block이 정상 전달되려면 -p 플래그가 반드시 필요하다
        cmd = [
            'claude',
            '-p',
            '--output-format', 'stream-json',
            '--input-format', 'stream-json',
            '--include-partial-messages',
            '--verbose',
            '--permission-mode', 'default',
            '--permission-prompt-tool', 'stdio',
        ]
        if extra_args:
            cmd.extend(extra_args)

        self._init_event.clear()

        # env_extras가 지정되면 현재 환경에 추가 환경변수를 병합
        proc_env = None
        if env_extras:
            proc_env = {**os.environ, **env_extras}

        try:
            self._process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                bufsize=1,
                env=proc_env,
            )
        except FileNotFoundError:
            self._status = 'stopped'
            return {
                'ok': False,
                'session_id': '',
                'error': 'claude CLI not found in PATH',
            }
        except OSError as e:
            self._status = 'stopped'
            return {
                'ok': False,
                'session_id': '',
                'error': str(e),
            }

        self._status = 'running'
        self._session_id = ''

        # stdout 읽기 데몬 스레드 시작
        self._stdout_thread = threading.Thread(
            target=self._read_stdout_loop,
            daemon=True,
            name='claude-stdout-reader',
        )
        self._stdout_thread.start()

        # init 대기 없이 즉시 응답 — SSE로 init 이벤트가 전달됨

        return {
            'ok': True,
            'session_id': self._session_id,
            'error': '',
        }

    def send_input(self, text: str, images: list[dict] | None = None) -> dict:
        """사용자 메시지를 Claude CLI stdin에 NDJSON 엔벨로프로 전송한다.

        Args:
            text: 전송할 사용자 메시지 텍스트
            images: 첨부 이미지 목록. 각 항목은 {"data": str, "media_type": str} 형태.
                    None이면 텍스트 전용 content 문자열로 구성한다.

        Returns:
            전송 결과 dict: {"ok": True/False, "error": str}
        """
        if not self._process or self._process.poll() is not None:
            # -p 모드에서 result 후 프로세스가 종료된 경우 --resume으로 자동 재시작
            if self._session_id:
                resume_args = ['--resume', self._session_id]
                self._init_event.clear()
                result = self.spawn(extra_args=resume_args)
                if not result.get('ok'):
                    return {'ok': False, 'error': f'respawn failed: {result.get("error", "")}'}
                # init 이벤트가 완료될 때까지 최대 10초 대기
                if not self._init_event.wait(timeout=10):
                    return {'ok': False, 'error': 'respawn init timeout'}
            else:
                return {'ok': False, 'error': 'process not running'}

        if images is not None:
            image_blocks = [
                {
                    'type': 'image',
                    'source': {
                        'type': 'base64',
                        'media_type': img['media_type'],
                        'data': img['data'],
                    },
                }
                for img in images
            ]
            content: str | list = (
                [{'type': 'text', 'text': text}] + image_blocks
                if text else image_blocks
            )
        else:
            content = text

        envelope = {
            'type': 'user',
            'message': {
                'role': 'user',
                'content': content,
            },
        }
        if self._session_id:
            envelope['session_id'] = self._session_id

        ndjson_line = json.dumps(envelope, ensure_ascii=False) + '\n'

        with self._stdin_lock:
            try:
                self._process.stdin.write(ndjson_line)
                self._process.stdin.flush()
            except (BrokenPipeError, OSError) as e:
                self._status = 'stopped'
                return {'ok': False, 'error': str(e)}

        return {'ok': True, 'error': ''}

    def send_permission_response(
        self,
        request_id: str,
        decision: str,
        session_id: str | None = None,
    ) -> dict:
        """permission 요청에 대한 control_response NDJSON을 stdin으로 전송한다.

        Args:
            request_id: 응답할 control_request의 request_id
            decision: "allow" 또는 "deny"
            session_id: 워크플로우 세션 ID (선택적). 지정 시 최상위 session_id 필드 추가.

        Returns:
            전송 결과 dict: {"ok": True/False, "error": str}
        """
        if not self._process or self._process.poll() is not None:
            return {'ok': False, 'error': 'process not running'}

        if decision == 'allow':
            response_body = {
                'subtype': 'success',
                'request_id': request_id,
                'response': {},
            }
        else:
            response_body = {
                'subtype': 'error',
                'request_id': request_id,
                'error': 'User denied permission',
            }

        envelope: dict = {
            'type': 'control_response',
            'response': response_body,
        }
        if session_id:
            envelope['session_id'] = session_id

        ndjson_line = json.dumps(envelope, ensure_ascii=False) + '\n'

        with self._stdin_lock:
            try:
                self._process.stdin.write(ndjson_line)
                self._process.stdin.flush()
            except (BrokenPipeError, OSError) as e:
                self._status = 'stopped'
                return {'ok': False, 'error': str(e)}

        return {'ok': True, 'error': ''}

    def interrupt(self) -> dict:
        """Claude CLI 프로세스에 SIGINT를 전송하여 현재 응답 생성만 중단한다.

        kill()과 달리 프로세스를 종료하지 않는다. SIGINT를 수신한 Claude CLI는
        현재 응답 생성을 중단하고 새 입력 대기 상태(idle)로 복귀한다.
        _status는 변경하지 않는다 — Claude CLI가 result 이벤트를 발행하면
        _read_stdout_loop에서 idle로 전환된다.

        Returns:
            결과 dict: {"ok": True/False, "error": str}
        """
        if not self._process:
            return {'ok': False, 'error': 'process not running'}

        if self._process.poll() is not None:
            self._status = 'stopped'
            self._process = None
            return {'ok': False, 'error': 'process not running'}

        try:
            os.kill(self._process.pid, signal.SIGINT)
        except OSError as e:
            return {'ok': False, 'error': str(e)}

        return {'ok': True, 'error': ''}

    def kill(self) -> dict:
        """Claude CLI 프로세스를 종료한다.

        SIGTERM으로 먼저 시도하고, 2초 내 종료되지 않으면 SIGKILL로 강제 종료한다.

        Returns:
            종료 결과 dict: {"ok": True/False, "error": str}
        """
        if not self._process:
            self._status = 'stopped'
            return {'ok': True, 'error': ''}

        if self._process.poll() is not None:
            self._status = 'stopped'
            self._process = None
            return {'ok': True, 'error': ''}

        try:
            self._process.terminate()
            try:
                self._process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=5)
        except OSError as e:
            return {'ok': False, 'error': str(e)}
        finally:
            self._status = 'stopped'
            self._process = None

        return {'ok': True, 'error': ''}

    @property
    def status(self) -> str:
        """프로세스 상태를 반환한다.

        Returns:
            "running", "idle", "stopped" 중 하나
        """
        if not self._process:
            return 'stopped'
        if self._process.poll() is not None:
            self._status = 'stopped'
            self._process = None
            return 'stopped'
        return self._status

    @property
    def session_id(self) -> str:
        """현재 세션 ID를 반환한다."""
        return self._session_id

    def _read_stdout_loop(self) -> None:
        """stdout에서 NDJSON 한 줄씩 읽어 파싱하고 SSE 채널로 브로드캐스트한다.

        프로세스 종료 또는 stdout EOF 시 루프를 빠져나온다.
        데몬 스레드에서 실행된다.
        """
        proc = self._process
        if not proc or not proc.stdout:
            return

        try:
            for line in proc.stdout:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    data = json.loads(stripped)
                except json.JSONDecodeError:
                    logger.debug('Non-JSON stdout line: %s', stripped[:200])
                    continue

                # system/init에서 session_id 추출 후 init 대기 이벤트 해제
                if (
                    data.get('type') == 'system'
                    and data.get('subtype') == 'init'
                ):
                    self._session_id = data.get('session_id', '')
                    self._model = data.get('model', '')
                    self._permission_mode = data.get('permissionMode', '')
                    if self._persist_file and self._session_id:
                        try:
                            with open(self._persist_file, 'w') as _pf:
                                _pf.write(self._session_id)
                        except OSError as _e:
                            logger.debug('session_id persist 실패: %s', _e)
                    self._init_event.set()

                # result 수신 시 상태를 idle로 전환
                if data.get('type') == 'result':
                    self._status = 'idle'

                self._channel.broadcast(data)
        except (ValueError, OSError):
            # 프로세스 종료 시 발생 가능
            pass
        finally:
            # 좀비 프로세스 방지: 명시적으로 wait() 호출
            try:
                proc.wait(timeout=5)
            except (subprocess.TimeoutExpired, OSError):
                pass

            # 프로세스가 종료된 경우 상태 업데이트
            if proc.poll() is not None:
                exit_code = proc.returncode
                # -p 모드에서 result 완료 후 정상 종료(exit_code 0)는
                # idle 상태로 전환하여 즉시 재입력 가능하게 한다.
                # 비정상 종료(exit_code != 0)만 stopped로 설정한다.
                if exit_code == 0:
                    self._status = 'idle'
                else:
                    self._status = 'stopped'
                # 종료 이벤트를 SSE로 알림
                self._channel.broadcast({
                    'type': 'system',
                    'subtype': 'process_exit',
                    'exit_code': exit_code,
                    'session_id': self._session_id,
                })
                # 비정상 종료 시 에러 이벤트도 전송
                if exit_code != 0:
                    self._channel.broadcast({
                        'type': 'error',
                        'message': f'Claude process exited with code {exit_code}',
                        'exit_code': exit_code,
                        'session_id': self._session_id,
                    })


# ---------------------------------------------------------------------------
# Poll Change Tracker
# ---------------------------------------------------------------------------

class PollChangeTracker:
    """폴링 클라이언트를 위한 변경 이벤트 축적기.

    마지막 폴링 이후 변경된 이벤트 타입별 파일명을 dict로 축적한다.
    flush() 호출 시 축적된 변경 내역을 반환하고 초기화한다.

    Attributes:
        _changes: 이벤트 타입 -> 변경 파일명 set 매핑
        _lock: thread-safe 접근용 Lock
    """

    def __init__(self) -> None:
        """초기화한다."""
        self._changes: dict[str, set[str]] = {}
        self._lock: threading.Lock = threading.Lock()

    def add(self, event_type: str, files: list[str]) -> None:
        """변경 이벤트 타입과 파일명 목록을 추가한다.

        Args:
            event_type: 추가할 이벤트 타입 (kanban, workflow, dashboard)
            files: 변경된 파일명 목록
        """
        with self._lock:
            if event_type not in self._changes:
                self._changes[event_type] = set()
            self._changes[event_type].update(files)

    def flush(self) -> dict[str, list[str]]:
        """축적된 변경 이벤트를 반환하고 초기화한다.

        Returns:
            이벤트 타입별 변경 파일명 목록 dict.
            예: {"kanban": ["T-038.xml"], "workflow": ["state.json"]}
            변경 없으면 빈 dict.
        """
        with self._lock:
            result = {k: list(v) for k, v in self._changes.items()}
            self._changes.clear()
            return result


# ---------------------------------------------------------------------------
# HTTP Request Handler
# ---------------------------------------------------------------------------

# 모듈 레벨 SSE 클라이언트 매니저 (서버 인스턴스와 공유)
sse_manager: SSEClientManager = SSEClientManager()

# 모듈 레벨 폴링 변경 추적기 (서버 인스턴스와 공유)
poll_tracker: PollChangeTracker = PollChangeTracker()

# 모듈 레벨 터미널 SSE 채널 및 Claude 프로세스 매니저
terminal_sse_channel: TerminalSSEChannel = TerminalSSEChannel()
claude_process: ClaudeProcess = ClaudeProcess(
    terminal_sse_channel,
    persist_file=os.path.join(os.getcwd(), '.claude.workflow', '.last-session-id'),
)


# ---------------------------------------------------------------------------
# Workflow Session Management (다중 워크플로우 세션)
# ---------------------------------------------------------------------------

@dataclass
class WorkflowSession:
    """워크플로우 세션 하나를 나타내는 데이터 클래스.

    각 워크플로우 티켓 실행은 독립된 ClaudeProcess와 TerminalSSEChannel을
    가지며, session_id로 식별된다.

    Attributes:
        session_id: 세션 고유 ID (형식: wf-T-NNN-timestamp)
        ticket_id: 칸반 티켓 ID (예: T-238)
        command: 실행 명령어 (implement, review, research 등)
        work_dir: 작업 디렉터리 절대 경로
        process: Claude CLI 프로세스 관리자 인스턴스
        channel: 터미널 SSE 브로드캐스트 채널 인스턴스
        created_at: 세션 생성 시각 (ISO 형식)
        current_step: 현재 진행 중인 워크플로우 단계 (예: PLAN, WORK, REPORT)
        last_artifact: 최근 생성된 산출물 경로 (예: work/W01-design.md)
    """

    session_id: str
    ticket_id: str
    command: str
    work_dir: str
    process: ClaudeProcess = field(repr=False)
    channel: TerminalSSEChannel = field(repr=False)
    created_at: str = field(default_factory=lambda: time.strftime('%Y-%m-%dT%H:%M:%S'))
    current_step: str = ''
    last_artifact: str = ''


class WorkflowSessionRegistry:
    """다중 워크플로우 세션 레지스트리.

    thread-safe하게 워크플로우 세션을 생성·조회·삭제한다.
    각 세션은 독립된 ClaudeProcess + TerminalSSEChannel 쌍을 보유한다.

    Attributes:
        _sessions: session_id -> WorkflowSession 매핑
        _lock: thread-safe 접근용 Lock
    """

    def __init__(self, persist_dir: str | None = None) -> None:
        """초기화한다.

        Args:
            persist_dir: 세션을 저장할 디렉터리. None이면 persist 비활성.
        """
        self._sessions: dict[str, WorkflowSession] = {}
        self._lock: threading.Lock = threading.Lock()
        self._persist_dir: str | None = persist_dir
        if self._persist_dir is not None:
            try:
                os.makedirs(self._persist_dir, exist_ok=True)
            except OSError:
                self._persist_dir = None

    def _session_file(self, session_id: str) -> str | None:
        """세션 이벤트 파일 경로를 반환한다."""
        if self._persist_dir is None:
            return None
        return os.path.join(self._persist_dir, f'{session_id}.jsonl')

    def create(
        self,
        ticket_id: str,
        command: str,
        work_dir: str,
    ) -> WorkflowSession:
        """새 워크플로우 세션을 생성한다.

        독립된 TerminalSSEChannel과 ClaudeProcess 인스턴스를 할당하고,
        session_id를 생성하여 레지스트리에 등록한다.

        Args:
            ticket_id: 칸반 티켓 ID (예: T-238)
            command: 실행 명령어 (implement, review, research 등)
            work_dir: 작업 디렉터리 절대 경로

        Returns:
            생성된 WorkflowSession 인스턴스
        """
        timestamp = time.strftime('%Y%m%d-%H%M%S')
        session_id = f'wf-{ticket_id}-{timestamp}'

        persist_path = self._session_file(session_id)
        channel = TerminalSSEChannel(persist_path=persist_path)
        process = ClaudeProcess(channel)

        session = WorkflowSession(
            session_id=session_id,
            ticket_id=ticket_id,
            command=command,
            work_dir=work_dir,
            process=process,
            channel=channel,
        )

        # 메타데이터를 파일 첫 줄에 기록
        if persist_path is not None:
            try:
                meta = {
                    '_meta': {
                        'session_id': session_id,
                        'ticket_id': ticket_id,
                        'command': command,
                        'work_dir': work_dir,
                        'created_at': session.created_at,
                    }
                }
                with open(persist_path, 'w', encoding='utf-8') as f:
                    f.write(json.dumps(meta, ensure_ascii=False) + '\n')
            except OSError:
                pass

        with self._lock:
            self._sessions[session_id] = session

        return session

    def load_from_disk(self) -> int:
        """persist 디렉터리에서 세션을 로드하여 레지스트리를 복원한다.

        각 *.jsonl 파일을 읽어:
          - 첫 줄의 _meta로 WorkflowSession 객체를 재생성
          - 나머지 줄의 이벤트들을 채널 히스토리에 복원
          - process는 새 ClaudeProcess (status='stopped')로 생성

        Returns:
            로드된 세션 개수
        """
        if self._persist_dir is None or not os.path.isdir(self._persist_dir):
            return 0

        loaded = 0
        for fname in sorted(os.listdir(self._persist_dir)):
            if not fname.endswith('.jsonl'):
                continue
            fpath = os.path.join(self._persist_dir, fname)
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
            except OSError:
                continue
            if not lines:
                continue
            try:
                first = json.loads(lines[0])
                meta = first.get('_meta')
                if not meta or not meta.get('session_id'):
                    continue
            except (json.JSONDecodeError, ValueError):
                continue

            channel = TerminalSSEChannel(persist_path=fpath)
            process = ClaudeProcess(channel)
            session = WorkflowSession(
                session_id=meta['session_id'],
                ticket_id=meta.get('ticket_id', ''),
                command=meta.get('command', ''),
                work_dir=meta.get('work_dir', ''),
                process=process,
                channel=channel,
                created_at=meta.get('created_at', time.strftime('%Y-%m-%dT%H:%M:%S')),
            )

            # 이벤트 복원 (파일 쓰기 없이 히스토리만)
            for line in lines[1:]:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    channel.replay_from_history(data)
                except (json.JSONDecodeError, ValueError):
                    continue

            with self._lock:
                self._sessions[session.session_id] = session
            loaded += 1

        return loaded

    def purge(self, session_id: str) -> bool:
        """세션을 레지스트리와 디스크에서 완전히 제거한다."""
        removed = self.remove(session_id)
        if removed and self._persist_dir is not None:
            fpath = self._session_file(session_id)
            if fpath and os.path.exists(fpath):
                try:
                    os.remove(fpath)
                except OSError:
                    pass
        return removed

    def get(self, session_id: str) -> WorkflowSession | None:
        """session_id로 세션을 조회한다.

        Args:
            session_id: 조회할 세션 ID

        Returns:
            WorkflowSession 인스턴스. 존재하지 않으면 None.
        """
        with self._lock:
            return self._sessions.get(session_id)

    def remove(self, session_id: str) -> bool:
        """세션을 레지스트리에서 제거한다.

        프로세스 종료는 호출자가 별도로 처리해야 한다.

        Args:
            session_id: 제거할 세션 ID

        Returns:
            제거 성공 시 True, 세션이 존재하지 않으면 False.
        """
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                return True
            return False

    def list_all(self) -> list[dict]:
        """전체 세션 목록을 dict 리스트로 반환한다.

        Returns:
            세션 메타데이터 dict 리스트. 각 dict 키:
            session_id, ticket_id, command, work_dir, status, created_at
        """
        with self._lock:
            return [
                {
                    'session_id': s.session_id,
                    'ticket_id': s.ticket_id,
                    'command': s.command,
                    'work_dir': s.work_dir,
                    'status': s.process.status,
                    'created_at': s.created_at,
                }
                for s in self._sessions.values()
            ]

    def get_by_ticket(self, ticket_id: str) -> WorkflowSession | None:
        """티켓 ID로 세션을 조회한다.

        동일 티켓에 여러 세션이 있을 경우 첫 번째 매칭을 반환한다.

        Args:
            ticket_id: 조회할 티켓 ID (예: T-238)

        Returns:
            WorkflowSession 인스턴스. 존재하지 않으면 None.
        """
        with self._lock:
            for session in self._sessions.values():
                if session.ticket_id == ticket_id:
                    return session
            return None


# 모듈 레벨 워크플로우 세션 레지스트리 싱글톤
workflow_registry: WorkflowSessionRegistry = WorkflowSessionRegistry()


class BoardHTTPRequestHandler(SimpleHTTPRequestHandler):
    """Board 전용 HTTP 요청 핸들러.

    /events 경로는 SSE 엔드포인트로 처리하고,
    /api/* 경로는 JSON API로 처리하고,
    그 외 경로는 SimpleHTTPRequestHandler의 정적 파일 서빙으로 위임한다.
    """

    def do_GET(self) -> None:
        """GET 요청을 처리한다."""
        if self.path == '/events':
            self._handle_sse()
        elif self.path == '/poll':
            self._handle_poll()
        elif self.path == '/terminal/events':
            self._handle_terminal_sse()
        elif self.path == '/terminal/status':
            self._handle_terminal_status()
        elif self.path == '/terminal/sessions':
            self._handle_terminal_sessions()
        elif self.path.startswith('/terminal/workflow/status'):
            self._handle_workflow_status()
        elif self.path.startswith('/terminal/workflow/events'):
            self._handle_workflow_sse()
        elif self.path == '/terminal/workflow/list':
            self._handle_workflow_list()
        elif self.path.startswith('/api/'):
            self._handle_api()
        else:
            super().do_GET()

    def do_POST(self) -> None:
        """POST 요청을 처리한다."""
        if self.path == '/api/env':
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            try:
                data = json.loads(body)
                ok = _update_env_value(os.getcwd(), data['key'], data['value'])
                self._send_json({'ok': ok})
            except (json.JSONDecodeError, KeyError):
                self.send_response(400)
                self.end_headers()
        elif self.path == '/api/restart':
            self._handle_restart()
        elif self.path == '/api/workflow/sync':
            self._handle_workflow_sync()
        elif self.path == '/terminal/start':
            self._handle_terminal_start()
        elif self.path == '/terminal/input':
            self._handle_terminal_input()
        elif self.path == '/terminal/interrupt':
            self._handle_terminal_interrupt()
        elif self.path == '/terminal/kill':
            self._handle_terminal_kill()
        elif self.path == '/terminal/workflow/start':
            self._handle_workflow_start()
        elif self.path == '/terminal/workflow/kill':
            self._handle_workflow_kill()
        elif self.path == '/terminal/workflow/input':
            self._handle_workflow_input()
        elif self.path == '/terminal/command':
            self._handle_terminal_command()
        elif self.path == '/terminal/permission':
            self._handle_terminal_permission()
        elif self.path == '/api/memory/file':
            self._handle_memory_write()
        elif self.path == '/api/prompt/rules/file':
            self._handle_rules_write()
        elif self.path == '/api/prompt/prompt-files/file':
            self._handle_prompt_write()
        elif self.path == '/api/prompt/claude-md':
            self._handle_claude_md_write()
        else:
            self.send_response(404)
            self.end_headers()

    def do_DELETE(self) -> None:
        """DELETE 요청을 처리한다."""
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path == '/api/memory/file':
            name = qs.get('name', [None])[0]
            if not name:
                self._send_error(400, 'Missing "name" query parameter')
                return
            try:
                self._send_json(
                    _delete_memory_file(os.getcwd(), name),
                )
            except ValueError as e:
                self._send_error(400, str(e))
            except FileNotFoundError as e:
                self._send_error(404, str(e))
        elif path == '/api/prompt/rules/file':
            rel_path = qs.get('path', [None])[0]
            if not rel_path:
                self._send_error(400, 'Missing "path" query parameter')
                return
            try:
                self._send_json(_delete_rules_file(os.getcwd(), rel_path))
            except ValueError as e:
                self._send_error(400, str(e))
            except FileNotFoundError as e:
                self._send_error(404, str(e))
            except RuntimeError as e:
                self._send_error(500, str(e))
        elif path == '/api/prompt/prompt-files/file':
            name = qs.get('name', [None])[0]
            if not name:
                self._send_error(400, 'Missing "name" query parameter')
                return
            try:
                self._send_json(_delete_prompt_file(os.getcwd(), name))
            except ValueError as e:
                self._send_error(400, str(e))
            except FileNotFoundError as e:
                self._send_error(404, str(e))
        else:
            self.send_response(404)
            self.end_headers()

    def _handle_memory_write(self) -> None:
        """메모리 파일 생성/수정 엔드포인트를 처리한다.

        POST /api/memory/file: 요청 본문 {"name": "filename.md", "content": "..."}
        """
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length == 0:
            self._send_error(400, 'Empty request body')
            return

        body = self.rfile.read(content_length)
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self._send_error(400, 'Invalid JSON')
            return

        name = data.get('name', '')
        content = data.get('content', '')
        if not name:
            self._send_error(400, 'Missing "name" field')
            return

        try:
            result = _write_memory_file(os.getcwd(), name, content)
            self._send_json(result)
        except ValueError as e:
            self._send_error(400, str(e))

    def _handle_rules_write(self) -> None:
        """rules 파일 생성/수정 엔드포인트를 처리한다.

        POST /api/prompt/rules/file: 요청 본문 {"path": "category/filename.md", "content": "..."}
        """
        data = self._read_json_body()
        if data is None:
            return

        rel_path = data.get('path', '')
        content = data.get('content', '')
        if not rel_path:
            self._send_error(400, 'Missing "path" field')
            return

        try:
            result = _write_rules_file(os.getcwd(), rel_path, content)
            self._send_json(result)
        except ValueError as e:
            self._send_error(400, str(e))
        except RuntimeError as e:
            self._send_error(500, str(e))

    def _handle_prompt_write(self) -> None:
        """prompt 파일 생성/수정 엔드포인트를 처리한다.

        POST /api/prompt/prompt-files/file: 요청 본문 {"name": "filename", "content": "..."}
        """
        data = self._read_json_body()
        if data is None:
            return

        name = data.get('name', '')
        content = data.get('content', '')
        if not name:
            self._send_error(400, 'Missing "name" field')
            return

        try:
            result = _write_prompt_file(os.getcwd(), name, content)
            self._send_json(result)
        except ValueError as e:
            self._send_error(400, str(e))

    def _handle_claude_md_write(self) -> None:
        """CLAUDE.md 수정 엔드포인트를 처리한다.

        POST /api/prompt/claude-md: 요청 본문 {"content": "..."}
        """
        data = self._read_json_body()
        if data is None:
            return

        content = data.get('content')
        if content is None:
            self._send_error(400, 'Missing "content" field')
            return

        result = _write_claude_md(os.getcwd(), content)
        self._send_json(result)

    def _handle_restart(self) -> None:
        """서버 재시작 요청을 처리한다.

        응답을 보낸 뒤 짧은 지연 후 현재 서버 소켓을 해제하고,
        새 서버 프로세스를 생성한 뒤 현재 프로세스를 종료한다.
        """
        self._send_json({'ok': True})

        def _do_restart() -> None:
            project_root = os.getcwd()
            url_file = os.path.join(
                project_root, '.claude.workflow', '.board.url',
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

    def _send_json(self, data: object) -> None:
        """JSON 응답을 전송한다."""
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def _handle_api(self) -> None:
        """API 요청을 라우팅한다."""
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)
        project_root = os.getcwd()

        if path == '/api/env':
            self._send_json(_parse_env_file(project_root))
        elif path == '/api/kanban':
            files_param = qs.get('files', [None])[0]
            files = files_param.split(',') if files_param else None
            self._send_json(_read_kanban_tickets(project_root, files))
        elif path == '/api/dashboard':
            self._send_json(_read_dashboard(project_root))
        elif path == '/api/workflow/entries':
            self._send_json(_list_workflow_entries(project_root))
        elif path == '/api/workflow/detail':
            entry = qs.get('entry', [None])[0]
            if not entry:
                self._send_json([])
                return
            self._send_json(_workflow_detail(project_root, entry))
        elif path == '/api/server-info':
            self._send_json({
                'pid': SERVER_PID,
                'started_at': SERVER_STARTED_AT,
            })
        elif path == '/api/branch':
            self._send_json({'branch': _get_git_branch(project_root)})
        elif path == '/api/workflow/artifact':
            self._handle_workflow_artifact(qs)
        elif path == '/api/memory':
            self._send_json(_list_memory_files(project_root))
        elif path == '/api/memory/file':
            name = qs.get('name', [None])[0]
            if not name:
                self._send_error(400, 'Missing "name" query parameter')
                return
            try:
                self._send_json(_read_memory_file(project_root, name))
            except ValueError as e:
                self._send_error(400, str(e))
            except FileNotFoundError as e:
                self._send_error(404, str(e))
        elif path == '/api/prompt/rules':
            self._send_json(_list_rules_files(project_root))
        elif path == '/api/prompt/rules/file':
            rel_path = qs.get('path', [None])[0]
            if not rel_path:
                self._send_error(400, 'Missing "path" query parameter')
                return
            try:
                self._send_json(_read_rules_file(project_root, rel_path))
            except ValueError as e:
                self._send_error(400, str(e))
            except FileNotFoundError as e:
                self._send_error(404, str(e))
        elif path == '/api/prompt/prompt-files':
            self._send_json(_list_prompt_files(project_root))
        elif path == '/api/prompt/prompt-files/file':
            name = qs.get('name', [None])[0]
            if not name:
                self._send_error(400, 'Missing "name" query parameter')
                return
            try:
                self._send_json(_read_prompt_file(project_root, name))
            except ValueError as e:
                self._send_error(400, str(e))
            except FileNotFoundError as e:
                self._send_error(404, str(e))
        elif path == '/api/prompt/claude-md':
            try:
                self._send_json(_read_claude_md(project_root))
            except FileNotFoundError as e:
                self._send_error(404, str(e))
        else:
            self.send_response(404)
            self.end_headers()

    def _handle_poll(self) -> None:
        """폴링 엔드포인트를 처리한다.

        마지막 폴링 이후 변경된 이벤트 타입 목록을 JSON으로 응답한다.
        """
        changes = poll_tracker.flush()
        body = json.dumps(changes).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def _handle_sse(self) -> None:
        """SSE 엔드포인트를 처리한다.

        연결을 유지하며 FileWatcher의 이벤트를 클라이언트에 스트리밍한다.
        """
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Connection', 'keep-alive')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        # 연결 확인용 초기 주석 전송
        try:
            self.wfile.write(b': connected\n\n')
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            return

        sse_manager.add(self.wfile)
        try:
            # 연결이 유지되는 동안 대기
            while True:
                time.sleep(1)
                # keep-alive 주석 전송으로 연결 상태 확인
                client_lock = sse_manager.get_lock(self.wfile)
                if client_lock is None:
                    break
                try:
                    with client_lock:
                        self.wfile.write(b': heartbeat\n\n')
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, OSError):
                    break
        finally:
            sse_manager.remove(self.wfile)

    # -- Terminal SSE / API handlers -----------------------------------------

    def _handle_terminal_sse(self) -> None:
        """터미널 전용 SSE 엔드포인트를 처리한다.

        /terminal/events 경로에 대해 TerminalSSEChannel로부터
        Claude CLI stdout 이벤트를 클라이언트에 스트리밍한다.
        기존 /events SSE와 완전히 독립된 채널을 사용한다.
        """
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Connection', 'keep-alive')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        # 연결 확인용 초기 주석 전송
        try:
            self.wfile.write(b': connected\n\n')
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            return

        # 재접속 시 last_event_id로 중복 재생 방지 (헤더 + 쿼리 파라미터)
        last_event_id = _resolve_last_event_id(self.headers, self.path)
        terminal_sse_channel.add(self.wfile, last_event_id=last_event_id)
        try:
            while True:
                time.sleep(1)
                client_lock = terminal_sse_channel.get_lock(self.wfile)
                if client_lock is None:
                    break
                try:
                    with client_lock:
                        self.wfile.write(b': heartbeat\n\n')
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, OSError):
                    break
        finally:
            terminal_sse_channel.remove(self.wfile)

    def _handle_terminal_status(self) -> None:
        """터미널 상태 조회 엔드포인트를 처리한다.

        GET /terminal/status: Claude 프로세스의 현재 상태를 JSON으로 응답한다.
        """
        project_root = os.getcwd()
        self._send_json({
            'status': claude_process.status,
            'session_id': claude_process.session_id,
            'last_session_id': claude_process.session_id,
            'model': claude_process._model,
            'permission_mode': claude_process._permission_mode,
            'branch': _get_git_branch(project_root),
            'clients': terminal_sse_channel.client_count,
        })

    def _handle_terminal_sessions(self) -> None:
        """세션 목록 조회 엔드포인트를 처리한다.

        GET /terminal/sessions: ~/.claude/projects/<project-path>/ 디렉터리에서
        .jsonl 파일을 mtime 기준 내림차순 최대 20개 스캔하여 JSON 배열로 반환한다.
        파일 내용을 읽지 않고 파일명(UUID)과 stat(mtime)만 활용한다.

        응답 항목:
            session_id: UUID (파일명에서 추출)
            last_active: mtime 기반 ISO 8601 형식 시각
            is_current: 현재 활성 세션과 일치 여부
        """
        project_root = os.getcwd()

        # cwd 기반으로 ~/.claude/projects/ 하위 디렉터리 경로 산출
        # 예: /home/deus/workspace/claude -> -home-deus-workspace-claude
        home_dir = os.path.expanduser('~')
        project_slug = project_root.replace('/', '-')
        sessions_dir = os.path.join(home_dir, '.claude', 'projects', project_slug)

        current_session_id = claude_process.session_id

        entries: list[tuple[float, str]] = []  # (mtime, session_id)
        try:
            with os.scandir(sessions_dir) as it:
                for entry in it:
                    if not entry.name.endswith('.jsonl'):
                        continue
                    stem = entry.name[:-6]  # ".jsonl" 제거
                    # UUID 형식 검증
                    try:
                        uuid.UUID(stem)
                    except ValueError:
                        continue
                    try:
                        mtime = entry.stat().st_mtime
                    except OSError:
                        continue
                    entries.append((mtime, stem))
        except OSError as e:
            logger.debug('세션 디렉터리 스캔 실패: %s', e)
            self._send_json([])
            return

        # mtime 내림차순 정렬 후 최대 20개 선택
        entries.sort(key=lambda x: x[0], reverse=True)
        entries = entries[:20]

        result = []
        for mtime, session_id in entries:
            last_active = datetime.datetime.fromtimestamp(
                mtime, tz=datetime.timezone.utc
            ).strftime('%Y-%m-%dT%H:%M:%SZ')
            result.append({
                'session_id': session_id,
                'last_active': last_active,
                'is_current': session_id == current_session_id,
            })

        self._send_json(result)

    def _handle_terminal_start(self) -> None:
        """터미널 세션 시작 엔드포인트를 처리한다.

        POST /terminal/start: Claude CLI 프로세스를 시작한다.
        요청 본문에 {"args": [...]} 형태로 추가 CLI 인자를 지정할 수 있다.
        """
        extra_args = None
        resume_session_id = None
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length > 0:
            body = self.rfile.read(content_length)
            try:
                data = json.loads(body)
                extra_args = data.get('args')
                resume_session_id = data.get('resume_session_id')
            except (json.JSONDecodeError, AttributeError):
                pass

        if resume_session_id:
            # UUID 형식 검증: 유효하지 않으면 새 세션으로 시작
            try:
                uuid.UUID(str(resume_session_id))
            except ValueError:
                logger.warning('유효하지 않은 resume_session_id: %s', resume_session_id)
                resume_session_id = None

        if resume_session_id:
            extra_args = ['--resume', resume_session_id]
        else:
            # 새 세션 시작 시에만 이전 이벤트 히스토리 초기화
            terminal_sse_channel.clear_history()

        result = claude_process.spawn(extra_args)
        self._send_json(result)

    def _handle_terminal_input(self) -> None:
        """터미널 입력 전송 엔드포인트를 처리한다.

        POST /terminal/input: 사용자 메시지를 Claude CLI에 전송한다.
        요청 본문: {"text": "사용자 메시지"}

        프로세스 미시작 시 409 Conflict를 반환한다.
        """
        if claude_process.status == 'stopped':
            self._send_error(409, 'Claude process not running')
            return

        content_length = int(self.headers.get('Content-Length', 0))
        if content_length == 0:
            self._send_error(400, 'Empty request body')
            return

        body = self.rfile.read(content_length)
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self._send_error(400, 'Invalid JSON')
            return

        text = data.get('text', '')
        images = data.get('images', None)

        if not text and not images:
            self._send_error(400, 'Missing "text" field')
            return

        if images is not None:
            validation_error = _validate_images(images)
            if validation_error:
                self._send_error(400, validation_error)
                return

        # 사용자 입력을 SSE 히스토리에 기록 (텍스트만, 이미지 base64 제외)
        if text:
            terminal_sse_channel.broadcast(
                {'type': 'user_input', 'text': text}
            )

        result = claude_process.send_input(text, images=images)
        self._send_json(result)

    def _handle_terminal_kill(self) -> None:
        """터미널 세션 종료 엔드포인트를 처리한다.

        POST /terminal/kill: Claude CLI 프로세스를 종료한다.

        프로세스 미시작 시 409 Conflict를 반환한다.
        """
        if claude_process.status == 'stopped':
            self._send_error(409, 'Claude process not running')
            return

        result = claude_process.kill()
        self._send_json(result)

    def _handle_terminal_command(self) -> None:
        """슬래시 명령어 전달 엔드포인트를 처리한다.

        POST /terminal/command: 클라이언트에서 전송한 슬래시 명령어를 Claude CLI stdin에
        전달한다. 기존 send_input() 메서드를 재사용하여 NDJSON 엔벨로프로 전송한다.

        요청 본문: {"command": "/clear"}
        선택 필드: "session_id" (현재 미사용, 메인 세션 전용)

        프로세스 미시작 시 409 Conflict를 반환한다.
        """
        if claude_process.status == 'stopped':
            self._send_error(409, 'Claude process not running')
            return

        content_length = int(self.headers.get('Content-Length', 0))
        if content_length == 0:
            self._send_error(400, 'Empty request body')
            return

        body = self.rfile.read(content_length)
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self._send_error(400, 'Invalid JSON')
            return

        command = data.get('command', '').strip()
        if not command:
            self._send_error(400, 'Missing "command" field')
            return

        if not command.startswith('/'):
            self._send_error(400, 'Command must start with "/"')
            return

        result = claude_process.send_input(command)
        self._send_json(result)

    def _handle_terminal_permission(self) -> None:
        """permission 요청에 대한 승인/거부 응답 엔드포인트를 처리한다.

        POST /terminal/permission
        요청 본문: {"request_id": "...", "decision": "allow"|"deny"}
        선택 필드: "session_id" (워크플로우 세션용)

        session_id가 있으면 workflow_registry에서 해당 세션의 프로세스를 사용하고,
        없으면 claude_process(메인 터미널)를 사용한다.

        프로세스 미실행 시 409 Conflict, 잘못된 요청 시 400 Bad Request를 반환한다.
        """
        data = self._read_json_body()
        if data is None:
            return

        request_id = data.get('request_id', '').strip()
        if not request_id:
            self._send_error(400, 'Missing "request_id" field')
            return

        decision = data.get('decision', '').strip()
        if decision not in ('allow', 'deny'):
            self._send_error(400, '"decision" must be "allow" or "deny"')
            return

        session_id = data.get('session_id', '').strip() or None

        if session_id:
            session = workflow_registry.get(session_id)
            if session is None:
                self._send_error(404, f'Session not found: {session_id}')
                return
            process = session.process
        else:
            process = claude_process

        if process.status == 'stopped':
            self._send_error(409, 'Claude process not running')
            return

        result = process.send_permission_response(request_id, decision, session_id)
        self._send_json(result)

    def _handle_terminal_interrupt(self) -> None:
        """현재 응답 생성 중단 엔드포인트를 처리한다.

        POST /terminal/interrupt: Claude CLI 프로세스에 SIGINT를 전송한다.
        프로세스를 종료하지 않고 현재 응답 생성만 중단한다.

        프로세스가 stopped 상태이면 409 Conflict를 반환한다.
        """
        if claude_process.status == 'stopped':
            self._send_error(409, 'Claude process not running')
            return

        result = claude_process.interrupt()
        self._send_json(result)

    # -- Workflow Session API handlers ----------------------------------------

    def _parse_query_param(self, key: str) -> str | None:
        """URL 쿼리 파라미터에서 지정한 키의 값을 추출한다.

        Args:
            key: 추출할 쿼리 파라미터 키

        Returns:
            파라미터 값 문자열. 존재하지 않으면 None.
        """
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(self.path)
        values = parse_qs(parsed.query).get(key)
        return values[0] if values else None

    def _read_json_body(self) -> dict | None:
        """POST 요청의 JSON 본문을 파싱하여 반환한다.

        파싱 실패 시 400 에러를 전송하고 None을 반환한다.

        Returns:
            파싱된 dict. 실패 시 None.
        """
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length == 0:
            self._send_error(400, 'Empty request body')
            return None

        body = self.rfile.read(content_length)
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self._send_error(400, 'Invalid JSON')
            return None

        if not isinstance(data, dict):
            self._send_error(400, 'Expected JSON object')
            return None

        return data

    def _handle_workflow_start(self) -> None:
        """워크플로우 세션 시작 엔드포인트를 처리한다.

        POST /terminal/workflow/start
        요청 본문: {"ticket": "T-NNN", "command": "implement", "work_dir": "/path/..."}

        워크플로우 레지스트리에 새 세션을 생성하고, Claude CLI 프로세스를 시작한다.
        프로세스 환경변수에 _WF_SESSION_TYPE, _WF_TICKET_ID, _WF_SESSION_ID,
        _WF_SERVER_PORT를 주입한다.
        """
        data = self._read_json_body()
        if data is None:
            return

        ticket = data.get('ticket', '')
        command = data.get('command', '')
        work_dir = data.get('work_dir', '')

        if not ticket:
            self._send_error(400, 'Missing "ticket" field')
            return
        if not command:
            self._send_error(400, 'Missing "command" field')
            return

        session = workflow_registry.create(ticket, command, work_dir)

        # 서버 포트 추출
        server_port = str(self.server.server_address[1])

        env_extras = {
            '_WF_SESSION_TYPE': 'workflow',
            '_WF_TICKET_ID': ticket,
            '_WF_SESSION_ID': session.session_id,
            '_WF_SERVER_PORT': server_port,
        }

        # 워크플로우 세션은 bypassPermissions 모드 유지 (블로킹 방지)
        spawn_result = session.process.spawn(
            extra_args=['--permission-mode', 'bypassPermissions'],
            env_extras=env_extras,
        )

        if not spawn_result.get('ok'):
            # 프로세스 시작 실패 시 레지스트리에서 제거
            workflow_registry.remove(session.session_id)
            self._send_error(500, spawn_result.get('error', 'Failed to start process'))
            return

        # CLI 초기화 완료까지 대기 (spawn 후 init 이벤트 수신 전 명령 유실 방지)
        if not session.process._init_event.wait(timeout=10):
            logger.warning("spawn init timeout after 10s, proceeding anyway")

        # launcher가 전달한 command를 세션에 자동 주입
        if command:
            session.process.send_input(command)

        self._send_json({
            'ok': True,
            'session_id': session.session_id,
        })

    def _handle_workflow_kill(self) -> None:
        """워크플로우 세션 프로세스를 종료한다. (세션 메타와 SSE 이력은 유지)

        POST /terminal/workflow/kill
        요청 본문: {"session_id": "wf-T-NNN-..."}
        선택 필드: "purge": true → 세션 메타까지 레지스트리에서 완전히 제거

        기본 동작: 프로세스만 kill, 세션/채널은 레지스트리에 남겨 SSE 재접속 시
        이력 재생이 가능하도록 유지한다. 명시적 purge 요청 시에만 완전 제거한다.
        """
        data = self._read_json_body()
        if data is None:
            return

        session_id = data.get('session_id', '')
        purge = bool(data.get('purge', False))
        if not session_id:
            self._send_error(400, 'Missing "session_id" field')
            return

        session = workflow_registry.get(session_id)
        if session is None:
            self._send_error(404, f'Session not found: {session_id}')
            return

        session.process.kill()
        if purge:
            workflow_registry.purge(session_id)

        self._send_json({'ok': True, 'purged': purge})

    def _handle_workflow_input(self) -> None:
        """워크플로우 세션 입력 전송 엔드포인트를 처리한다.

        POST /terminal/workflow/input
        요청 본문: {"session_id": "wf-T-NNN-...", "text": "사용자 메시지"}

        지정된 세션의 Claude CLI 프로세스에 사용자 메시지를 전송한다.
        """
        data = self._read_json_body()
        if data is None:
            return

        session_id = data.get('session_id', '')
        if not session_id:
            self._send_error(400, 'Missing "session_id" field')
            return

        text = data.get('text', '')
        images = data.get('images', None)

        if not text and not images:
            self._send_error(400, 'Missing "text" field')
            return

        if images is not None:
            validation_error = _validate_images(images)
            if validation_error:
                self._send_error(400, validation_error)
                return

        session = workflow_registry.get(session_id)
        if session is None:
            self._send_error(404, f'Session not found: {session_id}')
            return

        # 사용자 입력을 SSE 히스토리에 기록 (텍스트만, 이미지 base64 제외)
        if text:
            session.channel.broadcast(
                {'type': 'user_input', 'text': text}
            )

        result = session.process.send_input(text, images=images)
        self._send_json(result)

    def _handle_workflow_status(self) -> None:
        """워크플로우 세션 상태 조회 엔드포인트를 처리한다.

        GET /terminal/workflow/status?session_id=wf-T-NNN-...

        지정된 세션의 프로세스 상태와 메타데이터를 JSON으로 응답한다.
        """
        session_id = self._parse_query_param('session_id')
        if not session_id:
            self._send_error(400, 'Missing "session_id" query parameter')
            return

        session = workflow_registry.get(session_id)
        if session is None:
            self._send_error(404, f'Session not found: {session_id}')
            return

        self._send_json({
            'session_id': session.session_id,
            'ticket_id': session.ticket_id,
            'command': session.command,
            'work_dir': session.work_dir,
            'status': session.process.status,
            'created_at': session.created_at,
            'clients': session.channel.client_count,
            'current_step': session.current_step,
            'last_artifact': session.last_artifact,
        })

    def _handle_workflow_sse(self) -> None:
        """워크플로우 세션 전용 SSE 엔드포인트를 처리한다.

        GET /terminal/workflow/events?session_id=wf-T-NNN-...

        지정된 세션의 TerminalSSEChannel로부터 Claude CLI stdout 이벤트를
        클라이언트에 스트리밍한다. 기존 /terminal/events SSE와 동일한 패턴을 사용하되,
        세션별 독립 채널을 통해 멀티플렉싱한다.
        """
        session_id = self._parse_query_param('session_id')
        if not session_id:
            self._send_error(400, 'Missing "session_id" query parameter')
            return

        session = workflow_registry.get(session_id)
        if session is None:
            self._send_error(404, f'Session not found: {session_id}')
            return

        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Connection', 'keep-alive')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        # 연결 확인용 초기 주석 전송
        try:
            self.wfile.write(b': connected\n\n')
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            return

        # 재접속 시 last_event_id로 중복 재생 방지 (헤더 + 쿼리 파라미터)
        last_event_id = _resolve_last_event_id(self.headers, self.path)
        session.channel.add(self.wfile, last_event_id=last_event_id)
        try:
            while True:
                time.sleep(1)
                client_lock = session.channel.get_lock(self.wfile)
                if client_lock is None:
                    break
                try:
                    with client_lock:
                        self.wfile.write(b': heartbeat\n\n')
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, OSError):
                    break
        finally:
            session.channel.remove(self.wfile)

    def _handle_workflow_list(self) -> None:
        """워크플로우 세션 목록 조회 엔드포인트를 처리한다.

        GET /terminal/workflow/list

        현재 레지스트리에 등록된 모든 워크플로우 세션의 메타데이터를
        JSON 배열로 응답한다.
        """
        self._send_json(workflow_registry.list_all())

    def _handle_workflow_artifact(self, qs: dict) -> None:
        """워크플로우 산출물 파일 조회 엔드포인트를 처리한다.

        GET /api/workflow/artifact?session_id=wf-*&path=plan.md

        세션의 work_dir 하위 화이트리스트 파일만 plain text로 반환한다.
        화이트리스트: plan.md, report.md, work/*.md, skill-mapping.md

        경로 traversal 방지:
        - ``..`` 포함 경로 즉시 차단
        - ``os.path.realpath`` 정규화 후 work_dir prefix 검증
        - 화이트리스트 패턴 불일치 시 403 반환

        응답 헤더: Content-Type: text/markdown; charset=utf-8

        Args:
            qs: parse_qs 결과 dict (URL 쿼리 파라미터)

        Returns:
            None (응답 전송 후 종료)
        """
        import re as _re

        session_id_list = qs.get('session_id')
        path_list = qs.get('path')

        if not session_id_list or not path_list:
            self._send_error(404, 'Missing "session_id" or "path" query parameter')
            return

        session_id = session_id_list[0]
        rel_path = path_list[0]

        # 경로 traversal 조기 차단: '..' 포함 즉시 거부
        if '..' in rel_path:
            self._send_error(403, 'Path traversal detected')
            return

        # 세션 조회
        session = workflow_registry.get(session_id)
        if session is None:
            self._send_error(404, f'Session not found: {session_id}')
            return

        # work_dir 미설정 검증
        work_dir = session.work_dir
        if not work_dir:
            self._send_error(404, 'Session work_dir is not set')
            return

        # 화이트리스트 패턴 검증
        _WHITELIST_PATTERNS = [
            _re.compile(r'^plan\.md$'),
            _re.compile(r'^report\.md$'),
            _re.compile(r'^skill-mapping\.md$'),
            _re.compile(r'^work/[^/]+\.md$'),
        ]
        if not any(p.match(rel_path) for p in _WHITELIST_PATTERNS):
            self._send_error(403, f'Path not in whitelist: {rel_path}')
            return

        # work_dir realpath 정규화
        try:
            real_work_dir = os.path.realpath(work_dir)
        except (OSError, ValueError):
            self._send_error(404, 'Invalid work_dir')
            return

        # 파일 절대 경로 구성 + realpath 정규화
        candidate = os.path.join(real_work_dir, rel_path)
        try:
            real_candidate = os.path.realpath(candidate)
        except (OSError, ValueError):
            self._send_error(403, 'Invalid file path')
            return

        # work_dir prefix 검증 (symlink 우회 방지)
        if not real_candidate.startswith(real_work_dir + os.sep) and real_candidate != real_work_dir:
            self._send_error(403, 'Path escapes work_dir boundary')
            return

        # 파일 읽기
        if not os.path.isfile(real_candidate):
            self._send_error(404, f'File not found: {rel_path}')
            return

        try:
            with open(real_candidate, encoding='utf-8') as f:
                content = f.read()
        except OSError as exc:
            self._send_error(404, f'Cannot read file: {exc}')
            return

        body = content.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/markdown; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, code: int, message: str) -> None:
        """에러 응답을 JSON 형식으로 전송한다.

        Args:
            code: HTTP 상태 코드
            message: 에러 메시지
        """
        body = json.dumps(
            {'ok': False, 'error': message},
            ensure_ascii=False,
        ).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        """CORS preflight 요청을 처리한다."""
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Access-Control-Max-Age', '86400')
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        """로그 메시지를 출력한다. SSE 경로만 최소 로깅한다.

        Args:
            format: 로그 포맷 문자열
            *args: 포맷 인자
        """
        # 정적 파일 요청 로그 억제, SSE/터미널 관련만 로깅 (/poll 요청도 억제)
        if args and isinstance(args[0], str) and (
            '/events' in args[0] or '/terminal' in args[0]
        ):
            super().log_message(format, *args)

    def end_headers(self) -> None:
        """CORS 헤더를 추가한 후 헤더를 종료한다."""
        # SSE, poll, terminal 외 요청에도 CORS 헤더 추가 (index.html에서의 fetch 호환)
        # /events, /poll, /terminal/*은 각 핸들러에서 직접 CORS 헤더를 추가하므로 제외
        if self.path not in ('/events', '/poll') and not self.path.startswith('/terminal/'):
            self.send_header('Access-Control-Allow-Origin', '*')
        # JS/CSS 파일 캐시 방지
        if self.path.endswith(('.js', '.css')):
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        super().end_headers()


# ---------------------------------------------------------------------------
# Server startup
# ---------------------------------------------------------------------------

def is_port_in_use(port: int) -> bool:
    """포트가 사용 중인지 확인한다.

    Args:
        port: 확인할 포트 번호

    Returns:
        포트가 사용 중이면 True
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0


def _run_server(project_root: str) -> None:
    """서버를 실행한다. 포크된 자식 프로세스에서 호출된다.

    Args:
        project_root: 정적 파일 서빙의 루트 디렉터리
    """
    os.chdir(project_root)

    port = resolve_port(project_root)

    url_file = os.path.join(project_root, '.claude.workflow', '.board.url')

    # 터미널 세션 persist 파일 경로를 project_root 기준으로 재설정하고 복원
    last_session_file = os.path.join(project_root, '.claude.workflow', '.last-session-id')
    claude_process._persist_file = last_session_file
    if os.path.isfile(last_session_file):
        try:
            with open(last_session_file) as _sf:
                _saved_id = _sf.read().strip()
            if _saved_id:
                claude_process._session_id = _saved_id
                logger.debug('터미널 session_id 복원: %s', _saved_id)
        except OSError as _e:
            logger.debug('session_id 복원 실패: %s', _e)

    # 워크플로우 세션 persist 디렉터리 설정 + 디스크에서 복원
    sessions_dir = os.path.join(project_root, '.claude.workflow', '.sessions')
    workflow_registry._persist_dir = sessions_dir
    try:
        os.makedirs(sessions_dir, exist_ok=True)
    except OSError:
        pass
    loaded_count = workflow_registry.load_from_disk()
    if loaded_count > 0:
        print(f'[workflow_registry] {loaded_count}개 세션 복원 완료', file=sys.stderr)

    def _cleanup_runtime_files() -> None:
        """런타임 파일 .claude.workflow/.board.url을 삭제한다."""
        try:
            os.remove(url_file)
        except OSError:
            pass

    def _signal_handler(signum: int, frame: object) -> None:
        """SIGTERM/SIGINT 수신 시 Claude 프로세스와 런타임 파일을 정리하고 종료한다."""
        claude_process.kill()
        _cleanup_runtime_files()
        sys.exit(0)

    atexit.register(_cleanup_runtime_files)
    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    # 런타임 파일 생성 (디렉터리가 없으면 먼저 생성)
    os.makedirs(os.path.dirname(url_file), exist_ok=True)
    base = f'http://127.0.0.1:{port}/.claude.workflow/board'
    with open(url_file, 'w') as f:
        f.write(f'{base}/index.html\n{base}/terminal.html')

    # Memory 디렉터리를 WATCH_DIRS에 동적 등록 (절대경로 → os.path.join에서 그대로 사용됨)
    mem_dir = _resolve_memory_dir(project_root)
    if os.path.isdir(mem_dir):
        WATCH_DIRS[mem_dir] = 'memory'

    # FileWatcher 시작
    def on_change(event_type: str, files: list[str]) -> None:
        """파일 변경 감지 콜백."""
        sse_manager.broadcast(event_type, files)
        poll_tracker.add(event_type, files)

    watcher = FileWatcher(project_root, on_change)
    watcher_thread = threading.Thread(target=watcher.run, daemon=True)
    watcher_thread.start()

    # ThreadingHTTPServer 시작
    server = ThreadingHTTPServer(('0.0.0.0', port), BoardHTTPRequestHandler)
    server.daemon_threads = True
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        claude_process.kill()
        watcher.stop()
        server.shutdown()


def main() -> int:
    """서버를 백그라운드로 시작한다.

    .board.url 파일 존재 여부와 해당 포트 활성 상태로 중복 실행을 방지한다.

    Returns:
        종료 코드. 서버가 이미 실행 중이면 0, 성공 시 0.
    """
    project_root = os.path.normpath(
        os.path.join(os.path.dirname(__file__), '..', '..')
    )

    url_file = os.path.join(project_root, '.claude.workflow', '.board.url')

    if os.path.exists(url_file):
        try:
            from urllib.parse import urlparse
            with open(url_file) as f:
                recorded_url = f.read().strip().split('\n')[0]
            recorded_port = urlparse(recorded_url).port
            if recorded_port and is_port_in_use(recorded_port):
                # 서버가 이미 실행 중 — URL 파일만 갱신
                base = f'http://127.0.0.1:{recorded_port}/.claude.workflow/board'
                with open(url_file, 'w') as f:
                    f.write(f'{base}/index.html\n{base}/terminal.html')
                return 0
            else:
                # stale 파일: 포트가 비활성 상태이므로 파일 삭제 후 새로 시작
                try:
                    os.remove(url_file)
                except OSError:
                    pass
        except (ValueError, OSError):
            # 파일 읽기 실패 시 stale 처리
            pass

    # 자신을 --serve 모드로 백그라운드 실행
    subprocess.Popen(
        [sys.executable, __file__, '--serve', project_root],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return 0


if __name__ == '__main__':
    if len(sys.argv) >= 3 and sys.argv[1] == '--serve':
        _run_server(sys.argv[2])
    else:
        sys.exit(main())
