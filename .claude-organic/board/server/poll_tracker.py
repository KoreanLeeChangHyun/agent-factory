"""PollChangeTracker — diff-only polling state."""

from __future__ import annotations

import threading


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
