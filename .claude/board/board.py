#!/usr/bin/env -S python3 -u
"""Board HTTP server with SSE real-time updates.

ThreadingHTTPServer 기반 커스텀 서버로, 정적 파일 서빙과 /events SSE 엔드포인트를
동시 제공한다. FileWatcher가 감시 대상 디렉터리의 변경을 감지하여 SSE로 푸시한다.

감시 대상:
    .kanban/, .kanban/done/ -> kanban 이벤트
    .workflow/, .workflow/.history/ -> workflow 이벤트
    .dashboard/ -> dashboard 이벤트
"""

from __future__ import annotations

import atexit
import hashlib
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PORT_RANGE_START: int = 9900
PORT_RANGE_END: int = 9999
WATCH_INTERVAL: float = 1.0

# 감시 대상 경로 -> SSE 이벤트 타입 매핑
WATCH_DIRS: dict[str, str] = {
    '.kanban': 'kanban',
    os.path.join('.kanban', 'done'): 'kanban',
    '.workflow': 'workflow',
    os.path.join('.workflow', '.history'): 'workflow',
    '.dashboard': 'dashboard',
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


class BoardHTTPRequestHandler(SimpleHTTPRequestHandler):
    """Board 전용 HTTP 요청 핸들러.

    /events 경로는 SSE 엔드포인트로 처리하고,
    그 외 경로는 SimpleHTTPRequestHandler의 정적 파일 서빙으로 위임한다.
    """

    def do_GET(self) -> None:
        """GET 요청을 처리한다.

        /events 경로는 SSE 스트림으로, /poll 경로는 폴링 응답으로,
        나머지는 정적 파일로 응답한다.
        """
        if self.path == '/events':
            self._handle_sse()
        elif self.path == '/poll':
            self._handle_poll()
        else:
            super().do_GET()

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

    def log_message(self, format: str, *args: object) -> None:
        """로그 메시지를 출력한다. SSE 경로만 최소 로깅한다.

        Args:
            format: 로그 포맷 문자열
            *args: 포맷 인자
        """
        # 정적 파일 요청 로그 억제, SSE 관련만 로깅 (/poll 요청도 억제)
        if args and isinstance(args[0], str) and '/events' in args[0]:
            super().log_message(format, *args)

    def end_headers(self) -> None:
        """CORS 헤더를 추가한 후 헤더를 종료한다."""
        # SSE, poll 외 요청에도 CORS 헤더 추가 (board.html에서의 fetch 호환)
        # /events와 /poll은 각 핸들러에서 직접 CORS 헤더를 추가하므로 제외
        if self.path not in ('/events', '/poll'):
            self.send_header('Access-Control-Allow-Origin', '*')
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

    port_file = os.path.join(project_root, '.board.port')
    url_file = os.path.join(project_root, '.board.url')

    def _cleanup_runtime_files() -> None:
        """런타임 파일 .board.port와 .board.url을 삭제한다."""
        for path in (port_file, url_file):
            try:
                os.remove(path)
            except OSError:
                pass

    def _signal_handler(signum: int, frame: object) -> None:
        """SIGTERM/SIGINT 수신 시 런타임 파일을 정리하고 종료한다."""
        _cleanup_runtime_files()
        sys.exit(0)

    atexit.register(_cleanup_runtime_files)
    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    # 런타임 파일 생성
    with open(port_file, 'w') as f:
        f.write(str(port))
    with open(url_file, 'w') as f:
        f.write(f'http://127.0.0.1:{port}/.claude/board/board.html')

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
        watcher.stop()
        server.shutdown()


def main() -> int:
    """서버를 백그라운드로 시작한다.

    .board.port 파일 존재 여부와 해당 포트 활성 상태로 중복 실행을 방지한다.

    Returns:
        종료 코드. 서버가 이미 실행 중이면 0, 성공 시 0.
    """
    project_root = os.path.normpath(
        os.path.join(os.path.dirname(__file__), '..', '..')
    )

    port_file = os.path.join(project_root, '.board.port')

    if os.path.exists(port_file):
        try:
            with open(port_file) as f:
                recorded_port = int(f.read().strip())
            if is_port_in_use(recorded_port):
                # 서버가 이미 실행 중
                return 0
            else:
                # stale 파일: 포트가 비활성 상태이므로 파일 삭제 후 새로 시작
                url_file = os.path.join(project_root, '.board.url')
                for path in (port_file, url_file):
                    try:
                        os.remove(path)
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
