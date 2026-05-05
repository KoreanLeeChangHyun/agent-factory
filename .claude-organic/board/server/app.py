"""app module — resolve_port, is_port_in_use, _run_server."""

from __future__ import annotations

import atexit
import collections
import hashlib
import os
import signal
import socket
import sys
import threading
import time
from http.server import ThreadingHTTPServer

from ._common import (
    PORT_RANGE_START,
    PORT_RANGE_END,
    WATCH_INTERVAL,
    WATCH_DIRS,
    logger,
    _resolve_memory_dir,
)
from .http_router import BoardHTTPRequestHandler
from .sse_client_manager import FileWatcher, GitBranchWatcher, SSEClientManager
from .terminal_channel import TerminalSSEChannel
from .claude_process import ClaudeProcess
from .poll_tracker import PollChangeTracker
from .workflow_session import WorkflowSessionRegistry
from .state import (
    sse_manager,
    poll_tracker,
    terminal_sse_channel,
    claude_process,
    workflow_registry,
)


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

    url_file = os.path.join(project_root, '.claude-organic', '.board.url')

    # 터미널 세션 persist 파일 경로를 project_root 기준으로 재설정하고 복원
    last_session_file = os.path.join(project_root, '.claude-organic', '.last-session-id')
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
    sessions_dir = os.path.join(project_root, '.claude-organic', '.workflow-sessions')
    workflow_registry._persist_dir = sessions_dir
    try:
        os.makedirs(sessions_dir, exist_ok=True)
    except OSError:
        pass
    loaded_count = workflow_registry.load_from_disk()
    if loaded_count > 0:
        print(f'[workflow_registry] {loaded_count}개 세션 복원 완료', file=sys.stderr)

    def _cleanup_runtime_files() -> None:
        """런타임 파일 .claude-organic/.board.url을 삭제한다."""
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
    base = f'http://127.0.0.1:{port}'
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

    # GitBranchWatcher 시작 — `.git/HEAD` 변경 감지 → SSE git_branch 이벤트 push
    def on_branch_change(branch: str) -> None:
        sse_manager.broadcast('git_branch', data={'branch': branch})
        poll_tracker.add('git_branch', [branch])

    git_watcher = GitBranchWatcher(project_root, on_branch_change)
    git_watcher_thread = threading.Thread(target=git_watcher.run, daemon=True)
    git_watcher_thread.start()

    def _zombie_reaper_loop(interval: float = 60.0) -> None:
        """주기적으로 좀비 자식 프로세스를 reap한다.

        os.waitpid(-1, WNOHANG) 으로 블로킹 없이 이미 종료된 자식 프로세스를
        60초 주기로 수거한다. daemon=True 스레드로 동작하여 서버 종료 시 즉시 정리됨.
        """
        while True:
            count = 0
            try:
                while True:
                    pid, _status = os.waitpid(-1, os.WNOHANG)
                    if pid == 0:
                        break
                    count += 1
            except ChildProcessError:
                # 수거할 자식 프로세스 없음 — 정상 케이스
                pass
            if count > 0:
                logger.info('[zombie-gc] reaped %d child processes', count)
            time.sleep(interval)

    zombie_gc_thread = threading.Thread(
        target=_zombie_reaper_loop,
        name='zombie-gc',
        daemon=True,
    )
    zombie_gc_thread.start()
    logger.info('[zombie-gc] started — interval=60s')

    # ThreadingHTTPServer 시작
    server = ThreadingHTTPServer(('0.0.0.0', port), BoardHTTPRequestHandler)
    server.daemon_threads = True
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        claude_process.kill()
        watcher.stop()
        git_watcher.stop()
        server.shutdown()
