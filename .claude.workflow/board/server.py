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
from collections.abc import Callable
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

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
    """

    def __init__(self) -> None:
        """초기화한다."""
        self._clients: list = []
        self._lock: threading.Lock = threading.Lock()

    def add(self, wfile: object) -> None:
        """클라이언트를 추가한다.

        Args:
            wfile: HTTP 핸들러의 wfile (소켓 출력 스트림)
        """
        with self._lock:
            self._clients.append(wfile)

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

    def broadcast(self, event_type: str) -> None:
        """모든 클라이언트에 SSE 이벤트를 전송한다.

        전송 실패한 클라이언트(연결 끊김)는 목록에서 제거한다.

        Args:
            event_type: SSE 이벤트 타입 (kanban, workflow, dashboard)
        """
        timestamp = str(int(time.time()))
        message = f"event: {event_type}\ndata: {timestamp}\n\n"
        encoded = message.encode('utf-8')

        dead_clients: list = []
        with self._lock:
            for wfile in self._clients:
                try:
                    wfile.write(encoded)
                    wfile.flush()
                except (BrokenPipeError, ConnectionResetError, OSError):
                    dead_clients.append(wfile)

            for wfile in dead_clients:
                try:
                    self._clients.remove(wfile)
                except ValueError:
                    pass


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
}


class TerminalSSEChannel:
    """터미널 출력 전용 SSE 브로드캐스트 채널.

    SSEClientManager와 동일한 인터페이스로 독립 인스턴스를 생성하여,
    기존 /events SSE와 간섭 없이 /terminal/events 전용 스트림을 제공한다.

    NDJSON 청크를 SSE 이벤트로 변환하여 연결된 모든 클라이언트에 전송한다.

    Attributes:
        _clients: 연결된 클라이언트의 wfile 객체 목록
        _lock: 클라이언트 목록 접근용 Lock
    """

    def __init__(self) -> None:
        """초기화한다."""
        self._clients: list = []
        self._lock: threading.Lock = threading.Lock()

    def add(self, wfile: object) -> None:
        """클라이언트를 추가한다.

        Args:
            wfile: HTTP 핸들러의 wfile (소켓 출력 스트림)
        """
        with self._lock:
            self._clients.append(wfile)

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

    def broadcast(self, data: dict) -> None:
        """NDJSON 메시지를 SSE 이벤트로 변환하여 모든 클라이언트에 전송한다.

        메시지 타입에 따라 적절한 SSE 이벤트 이름을 결정한다:
        - stream_event (text_delta) -> event: stdout
        - stream_event (input_json_delta) -> event: stdout
        - result -> event: result
        - system -> event: system
        - control_request -> event: permission
        - 기타 -> event: stdout (기본값)

        전송 실패한 클라이언트(연결 끊김)는 목록에서 제거한다.

        Args:
            data: 파싱된 NDJSON 메시지 dict
        """
        event_name = self._classify_event(data)
        payload = self._build_payload(data, event_name)
        json_payload = json.dumps(payload, ensure_ascii=False)
        message = f"event: {event_name}\ndata: {json_payload}\n\n"
        encoded = message.encode('utf-8')

        dead_clients: list = []
        with self._lock:
            for wfile in self._clients:
                try:
                    wfile.write(encoded)
                    wfile.flush()
                except (BrokenPipeError, ConnectionResetError, OSError):
                    dead_clients.append(wfile)

            for wfile in dead_clients:
                try:
                    self._clients.remove(wfile)
                except ValueError:
                    pass

    def _classify_event(self, data: dict) -> str:
        """NDJSON 메시지 타입으로부터 SSE 이벤트 이름을 결정한다.

        Args:
            data: 파싱된 NDJSON 메시지 dict

        Returns:
            SSE 이벤트 이름 문자열
        """
        msg_type = data.get('type', '')

        if msg_type == 'stream_event':
            delta_type = (
                data.get('event', {}).get('delta', {}).get('type', '')
            )
            return _NDJSON_EVENT_MAP.get(delta_type, 'stdout')

        if msg_type == 'assistant':
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
        if event_name == 'stdout':
            return self._build_stdout_payload(data)
        if event_name == 'result':
            return self._build_result_payload(data)
        if event_name == 'system':
            return self._build_system_payload(data)
        if event_name == 'permission':
            return {
                'kind': 'permission',
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
            # content_block_start, message_start 등 기타 stream_event
            return {
                'kind': event.get('type', 'stream_event'),
                'raw': event,
            }

        if msg_type == 'assistant':
            content = data.get('message', {}).get('content', [])
            text_parts = [
                block.get('text', '')
                for block in content
                if block.get('type') == 'text'
            ]
            return {
                'kind': 'assistant',
                'text': ''.join(text_parts),
            }

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

    def __init__(self, channel: TerminalSSEChannel) -> None:
        """초기화한다.

        Args:
            channel: NDJSON 이벤트를 브로드캐스트할 TerminalSSEChannel 인스턴스
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

    def spawn(self, extra_args: list[str] | None = None) -> dict:
        """Claude CLI 프로세스를 시작한다.

        이미 실행 중인 프로세스가 있으면 먼저 종료한다.
        프로세스 시작 후 system/init SSE 이벤트를 최대 10초까지 대기하여
        session_id를 응답에 포함한다.

        Args:
            extra_args: 추가 CLI 인자 목록 (선택적)

        Returns:
            시작 결과 dict: {"ok": True/False, "session_id": str, "error": str}
        """
        if self._process and self._process.poll() is None:
            self.kill()
            self._init_event.clear()

        # 이전 stdout 스레드가 완전히 종료될 때까지 대기
        if self._stdout_thread and self._stdout_thread.is_alive():
            self._stdout_thread.join(timeout=3)

        # stdin 대기 모드로 시작: --print와 -p '' 제거
        # --input-format stream-json만 사용하면 Claude는 stdin에서 NDJSON 입력을 대기한다
        cmd = [
            'claude',
            '--output-format', 'stream-json',
            '--input-format', 'stream-json',
            '--include-partial-messages',
            '--verbose',
        ]
        if extra_args:
            cmd.extend(extra_args)

        self._init_event.clear()

        try:
            self._process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
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

    def send_input(self, text: str) -> dict:
        """사용자 메시지를 Claude CLI stdin에 NDJSON 엔벨로프로 전송한다.

        Args:
            text: 전송할 사용자 메시지 텍스트

        Returns:
            전송 결과 dict: {"ok": True/False, "error": str}
        """
        if not self._process or self._process.poll() is not None:
            return {'ok': False, 'error': 'process not running'}

        envelope = {
            'type': 'user',
            'message': {
                'role': 'user',
                'content': text,
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
claude_process: ClaudeProcess = ClaudeProcess(terminal_sse_channel)


KANBAN_DIRS_LIST: list[str] = ['open', 'progress', 'review', 'done']
WF_BASE: str = os.path.join('.claude.workflow', 'workflow')
WF_HISTORY: str = os.path.join('.claude.workflow', 'workflow', '.history')
DASH_BASE: str = os.path.join('.claude.workflow', 'dashboard')
DASH_FILES: list[str] = ['usage', 'logs', 'skills']
WF_ENTRY_RE = __import__('re').compile(r'^\d{8}-\d{6}$')
WF_DETAIL_FILES: list[dict] = [
    {'key': 'query',   'file': 'user_prompt.txt'},
    {'key': 'plan',    'file': 'plan.md'},
    {'key': 'report',  'file': 'report.md'},
    {'key': 'summary', 'file': 'summary.txt'},
    {'key': 'usage',   'file': 'usage.json'},
    {'key': 'log',     'file': 'workflow.log'},
]


def _resolve_settings_file(project_root: str) -> str:
    """Return .settings if exists, else .env (fallback)."""
    settings = os.path.join(project_root, '.claude.workflow', '.settings')
    if os.path.exists(settings):
        return settings
    return os.path.join(project_root, '.claude.workflow', '.env')


def _parse_env_file(project_root: str) -> list[dict]:
    """Parse .settings/.env into structured sections for the settings UI."""
    env_file = _resolve_settings_file(project_root)
    if not os.path.exists(env_file):
        return []

    sections: dict[str, list[dict]] = {}
    section_order: list[str] = []
    current_section = '기타'
    pending_comment = ''

    with open(env_file, encoding='utf-8') as f:
        for line in f:
            stripped = line.strip()

            # Section header: "# (N) Section Name"
            if stripped.startswith('# (') and ')' in stripped:
                current_section = stripped.split(')', 1)[1].strip()
                if current_section not in sections:
                    sections[current_section] = []
                    section_order.append(current_section)
                pending_comment = ''
                continue

            if stripped.startswith('# ---'):
                continue

            if stripped.startswith('#'):
                text = stripped[1:].strip()
                if text.startswith('용도:'):
                    pending_comment = text[3:].strip()
                continue

            if not stripped or '=' not in stripped:
                continue

            key, _, rest = stripped.partition('=')
            key = key.strip()

            # Extract inline comment (2+ spaces before #)
            value = rest
            inline_comment = ''
            m = __import__('re').match(r'^(.*?)\s{2,}#\s*(.*)', rest)
            if m:
                value = m.group(1).strip()
                inline_comment = m.group(2).strip()
            else:
                value = rest.strip()

            # Detect type
            var_type = 'string'
            if value.lower() in ('true', 'false'):
                var_type = 'bool'
            elif value.isdigit():
                var_type = 'int'
            else:
                try:
                    float(value)
                    if '.' in value:
                        var_type = 'float'
                except ValueError:
                    pass

            label = inline_comment or pending_comment or ''
            if current_section not in sections:
                sections[current_section] = []
                section_order.append(current_section)

            sections[current_section].append({
                'key': key,
                'value': value,
                'type': var_type,
                'label': label,
            })
            pending_comment = ''

    return [{'section': s, 'vars': sections[s]} for s in section_order]


def _update_env_value(project_root: str, key: str, new_value: str) -> bool:
    """Update a single key's value in .settings/.env, preserving structure and comments."""
    env_file = _resolve_settings_file(project_root)
    if not os.path.exists(env_file):
        return False

    with open(env_file, encoding='utf-8') as f:
        lines = f.readlines()

    _re = __import__('re')
    pattern = _re.compile(r'^' + _re.escape(key) + r'=')

    for i, line in enumerate(lines):
        if not pattern.match(line.strip()):
            continue

        old_rest = line.strip().split('=', 1)[1]
        inline_part = ''
        m = _re.match(r'^(.*?)\s{2,}(#\s*.*)', old_rest)
        if m:
            inline_part = m.group(2)

        if inline_part:
            base = f"{key}={new_value}"
            pad = max(2, 40 - len(base))
            lines[i] = base + ' ' * pad + inline_part + '\n'
        else:
            lines[i] = f"{key}={new_value}\n"
        break
    else:
        return False

    with open(env_file, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    return True


def _read_kanban_tickets(
    project_root: str, files: list[str] | None = None,
) -> dict[str, str | None]:
    """kanban 디렉터리에서 XML 티켓을 읽어 {파일명: 내용} dict를 반환한다."""
    kanban = os.path.join(project_root, '.claude.workflow', 'kanban')
    result: dict[str, str | None] = {}
    for d in KANBAN_DIRS_LIST:
        dp = os.path.join(kanban, d)
        if not os.path.isdir(dp):
            continue
        try:
            for e in os.scandir(dp):
                if not e.is_file() or not e.name.endswith('.xml'):
                    continue
                if files and e.name not in files:
                    continue
                if e.name in result:
                    continue
                try:
                    with open(e.path, encoding='utf-8') as f:
                        result[e.name] = f.read()
                except OSError:
                    result[e.name] = None
        except OSError:
            pass
    if files:
        for fn in files:
            if fn not in result:
                result[fn] = None
    return result


def _read_dashboard(project_root: str) -> dict[str, str]:
    """dashboard .md 파일 3개를 읽어 반환한다."""
    base = os.path.join(project_root, DASH_BASE)
    result: dict[str, str] = {}
    for name in DASH_FILES:
        path = os.path.join(base, f'.{name}.md')
        try:
            with open(path, encoding='utf-8') as f:
                result[name] = f.read()
        except OSError:
            result[name] = ''
    return result


def _list_workflow_entries(project_root: str) -> list[str]:
    """workflow + .history 엔트리를 최신순 정렬하여 반환한다."""
    entries: list[str] = []
    for rel in (WF_BASE, WF_HISTORY):
        abs_dir = os.path.join(project_root, rel)
        if not os.path.isdir(abs_dir):
            continue
        prefix = rel + '/'
        try:
            for e in os.scandir(abs_dir):
                if e.is_dir() and WF_ENTRY_RE.match(e.name):
                    entries.append(prefix + e.name + '/')
        except OSError:
            pass
    entries.sort(key=lambda p: p.rstrip('/').rsplit('/', 1)[-1], reverse=True)
    return entries


def _workflow_detail(project_root: str, entry_rel: str) -> list[dict]:
    """워크플로우 엔트리 1개의 상세 정보를 반환한다."""
    entry_name = entry_rel.rstrip('/').rsplit('/', 1)[-1]
    entry_abs = os.path.join(project_root, entry_rel.strip('/'))
    if not os.path.isdir(entry_abs):
        return []
    items: list[dict] = []
    try:
        task_dirs = sorted(
            (e.name for e in os.scandir(entry_abs) if e.is_dir()),
        )
    except OSError:
        return []
    for task in task_dirs:
        task_abs = os.path.join(entry_abs, task)
        try:
            cmd_dirs = sorted(
                (e.name for e in os.scandir(task_abs) if e.is_dir()),
            )
        except OSError:
            continue
        for cmd in cmd_dirs:
            cmd_abs = os.path.join(task_abs, cmd)
            status_path = os.path.join(cmd_abs, 'status.json')
            if not os.path.isfile(status_path):
                continue
            try:
                with open(status_path, encoding='utf-8') as f:
                    status = json.load(f)
            except (OSError, json.JSONDecodeError):
                continue
            # basePath: relative URL matching client convention
            base_path = entry_rel + task + '/' + cmd + '/'
            # file map
            file_map: dict = {}
            for wf in WF_DETAIL_FILES:
                fp = os.path.join(cmd_abs, wf['file'])
                exists = os.path.isfile(fp)
                file_map[wf['key']] = {
                    'exists': exists,
                    'url': base_path + wf['file'] if exists else '',
                }
            work_dir = os.path.join(cmd_abs, 'work')
            has_work = os.path.isdir(work_dir)
            file_map['work'] = {
                'exists': has_work,
                'url': base_path + 'work/' if has_work else '',
                'isDir': True,
            }
            items.append({
                'entry': entry_name,
                'task': task,
                'command': cmd,
                'basePath': base_path,
                'step': status.get('step', 'NONE'),
                'created_at': status.get('created_at', ''),
                'updated_at': status.get('updated_at', ''),
                'transitions': status.get('transitions', []),
                'fileMap': file_map,
            })
    return items


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
        elif self.path == '/terminal/start':
            self._handle_terminal_start()
        elif self.path == '/terminal/input':
            self._handle_terminal_input()
        elif self.path == '/terminal/kill':
            self._handle_terminal_kill()
        else:
            self.send_response(404)
            self.end_headers()

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
            try:
                result = subprocess.run(
                    ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                    capture_output=True, text=True, timeout=3,
                    cwd=project_root,
                )
                branch = result.stdout.strip() if result.returncode == 0 else ''
            except (FileNotFoundError, subprocess.TimeoutExpired):
                branch = ''
            self._send_json({'branch': branch})
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
        self.send_header('Content-Type', 'text/event-stream')
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
                try:
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
        self.send_header('Content-Type', 'text/event-stream')
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

        terminal_sse_channel.add(self.wfile)
        try:
            while True:
                time.sleep(1)
                try:
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
        self._send_json({
            'status': claude_process.status,
            'session_id': claude_process.session_id,
            'model': claude_process._model,
            'permission_mode': claude_process._permission_mode,
            'clients': terminal_sse_channel.client_count,
        })

    def _handle_terminal_start(self) -> None:
        """터미널 세션 시작 엔드포인트를 처리한다.

        POST /terminal/start: Claude CLI 프로세스를 시작한다.
        요청 본문에 {"args": [...]} 형태로 추가 CLI 인자를 지정할 수 있다.
        """
        extra_args = None
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length > 0:
            body = self.rfile.read(content_length)
            try:
                data = json.loads(body)
                extra_args = data.get('args')
            except (json.JSONDecodeError, AttributeError):
                pass

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
        if not text:
            self._send_error(400, 'Missing "text" field')
            return

        result = claude_process.send_input(text)
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
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
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
    terminal_url_file = os.path.join(project_root, '.claude.workflow', '.terminal.url')

    def _cleanup_runtime_files() -> None:
        """런타임 파일 .claude.workflow/.board.url, .terminal.url을 삭제한다."""
        for f in (url_file, terminal_url_file):
            try:
                os.remove(f)
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
    with open(terminal_url_file, 'w') as f:
        f.write(f'{base}/terminal.html')

    # FileWatcher 시작
    def on_change(event_type: str, files: list[str]) -> None:
        """파일 변경 감지 콜백."""
        sse_manager.broadcast(event_type)
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
