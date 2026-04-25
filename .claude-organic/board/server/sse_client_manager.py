"""FileWatcher + SSEClientManager for kanban/workflow/dashboard SSE."""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from collections.abc import Callable

from ._common import WATCH_DIRS, WATCH_INTERVAL, logger
from board_data import _get_git_branch


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
# Git Branch Watcher
# ---------------------------------------------------------------------------


class GitBranchWatcher:
    """현재 git 브랜치 변경 감시기.

    `.git/HEAD` 파일의 mtime 을 짧은 주기로 폴링하여 변경이 감지될 때만
    `_get_git_branch()` 로 브랜치명을 재조회하고, 직전 값과 다르면 콜백을 호출한다.
    HEAD 파일이 바뀌는 순간(checkout/branch 전환)만 git 명령을 실행하므로
    상시 부하가 거의 없다.

    worktree(`.git` 가 파일인 경우)도 mtime 추적 후 subprocess 폴백으로 정상 동작한다.

    Attributes:
        _project_root: 프로젝트 루트 절대 경로
        _on_change: 브랜치 변경 시 호출할 콜백 Callable[[str], None]
        _running: 감시 루프 실행 플래그
        _last_branch: 직전 감시한 브랜치명
        _last_head_mtime: 직전 .git/HEAD 의 mtime
        _head_path: `.git/HEAD` 절대 경로
    """

    def __init__(
        self,
        project_root: str,
        on_change: Callable[[str], None],
    ) -> None:
        """초기화한다.

        Args:
            project_root: 프로젝트 루트 절대 경로
            on_change: 브랜치 변경 시 호출할 콜백, 새 브랜치명을 인자로 받음
        """
        self._project_root: str = project_root
        self._on_change: Callable[[str], None] = on_change
        self._running: bool = False
        self._last_branch: str = _get_git_branch(project_root)
        self._head_path: str = os.path.join(project_root, '.git', 'HEAD')
        self._last_head_mtime: float = self._read_head_mtime()

    def _read_head_mtime(self) -> float:
        """.git/HEAD 의 mtime 을 반환한다. 없으면 0.0."""
        try:
            return os.stat(self._head_path).st_mtime
        except OSError:
            return 0.0

    def run(self) -> None:
        """감시 루프를 실행한다. daemon 스레드에서 호출된다."""
        self._running = True
        while self._running:
            time.sleep(WATCH_INTERVAL)
            self._check()

    def stop(self) -> None:
        """감시 루프를 중지한다."""
        self._running = False

    def _check(self) -> None:
        """HEAD mtime 변화 시에만 브랜치를 재조회하고 변경 시 콜백 호출."""
        mtime = self._read_head_mtime()
        if mtime == self._last_head_mtime:
            return
        self._last_head_mtime = mtime
        new_branch = _get_git_branch(self._project_root)
        if new_branch and new_branch != self._last_branch:
            self._last_branch = new_branch
            try:
                self._on_change(new_branch)
            except Exception:  # noqa: BLE001 — 콜백 실패가 watcher 죽이지 않도록
                logger.exception('GitBranchWatcher on_change 콜백 실패')


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

    def broadcast(
        self,
        event_type: str,
        files: list | None = None,
        data: dict | None = None,
    ) -> None:
        """모든 클라이언트에 SSE 이벤트를 전송한다.

        전송 실패한 클라이언트(연결 끊김)는 목록에서 제거한다.
        per-client lock으로 heartbeat 루프와의 concurrent write를 방지한다.

        Args:
            event_type: SSE 이벤트 타입 (kanban, workflow, dashboard, git_branch 등)
            files: 변경된 파일 목록. kanban 이벤트 시 data 필드에 JSON으로 포함됨.
            data: 임의 payload dict. files 보다 우선 적용됨.
                  files 와 data 모두 None 이면 타임스탬프 문자열을 data로 전송.
        """
        if data is not None:
            body = json.dumps(data)
        elif files is not None:
            body = json.dumps({"files": files})
        else:
            body = str(int(time.time()))
        message = f"event: {event_type}\ndata: {body}\n\n"
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
    'rate_limit_event': 'rate_limit',  # T-389: G-2 해소
}
