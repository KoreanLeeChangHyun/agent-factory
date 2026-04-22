"""stuck_detector.py - 워크플로우 stuck 패턴 감지 모듈.

슬라이딩 윈도우 기반 3가지 패턴으로 워크플로우가 stuck 상태에 빠졌는지
감지하고, 감지 시 workflow.log에 WARN을 기록한다.

패턴:
    규칙 1 (연속 오류): 슬라이딩 윈도우 내 모든 이벤트가 failed 상태.
    규칙 2 (반복 key): 동일 task_id가 3회 이상 failed로 반복.
    규칙 3 (진동 패턴): running->failed 교대가 4회 이상.

비차단 원칙:
    check_stuck()은 모든 예외를 조용히 흡수한다.
    감지 실패 시에도 워크플로우 상태 전이에 영향을 주지 않는다.

사용 예:
    from flow.stuck_detector import check_stuck

    check_stuck(abs_work_dir, "W01", "failed")
"""
from __future__ import annotations

import os
import sys
from collections import Counter
from datetime import datetime

_scripts_dir: str = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
)
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from common import atomic_write_json, load_json_file
from data.constants import KST
from flow.flow_logger import append_log as _append_log


class StuckDetector:
    """슬라이딩 윈도우 기반 stuck 패턴 감지기.

    status.json의 task_events 배열에 이벤트를 기록하고,
    최근 window_size개 이벤트를 분석하여 stuck 패턴을 감지한다.

    Attributes:
        work_dir: 워크플로우 절대 경로 (status.json 위치).
        window_size: 슬라이딩 윈도우 크기 (기본 6).
    """

    def __init__(self, work_dir: str, window_size: int = 6) -> None:
        """StuckDetector 초기화.

        Args:
            work_dir: 워크플로우 절대 경로. status.json이 위치하는 디렉터리.
            window_size: 슬라이딩 윈도우 크기. 최근 N개 이벤트만 감지에 사용.
        """
        self.work_dir = work_dir
        self.window_size = window_size
        self._status_file = os.path.join(work_dir, "status.json")

    def _load_events(self) -> list[dict]:
        """status.json의 task_events 배열에서 최근 window_size개 이벤트를 로드한다.

        Returns:
            최근 window_size개 이벤트 딕셔너리 리스트.
            status.json이 없거나 task_events 필드가 없으면 빈 리스트 반환.
        """
        data = load_json_file(self._status_file)
        if not isinstance(data, dict):
            return []
        events = data.get("task_events", [])
        if not isinstance(events, list):
            return []
        return events[-self.window_size:]

    def _save_event(self, event: dict) -> None:
        """이벤트를 status.json의 task_events 배열에 추가한다.

        슬라이딩 윈도우 원칙을 적용하여 window_size * 2개 이상이면
        오래된 이벤트를 잘라낸다 (메모리/디스크 부담 최소화).

        Args:
            event: 기록할 이벤트 딕셔너리. {task_id, status, timestamp} 구조.
        """
        if not os.path.exists(self._status_file):
            return

        data = load_json_file(self._status_file)
        if not isinstance(data, dict):
            return

        if "task_events" not in data or not isinstance(data.get("task_events"), list):
            data["task_events"] = []

        data["task_events"].append(event)

        # 오래된 이벤트 정리: window_size * 2 초과 시 앞에서부터 잘라냄
        max_keep = self.window_size * 2
        if len(data["task_events"]) > max_keep:
            data["task_events"] = data["task_events"][-max_keep:]

        atomic_write_json(self._status_file, data)

    def record_event(self, task_id: str, status: str) -> None:
        """태스크 이벤트를 status.json에 기록한다.

        Args:
            task_id: 태스크 ID (예: 'W01', 'W02').
            status: 태스크 상태 (예: 'running', 'failed', 'completed').
        """
        now: str = datetime.now(KST).strftime("%Y-%m-%dT%H:%M:%S+09:00")
        event = {
            "task_id": task_id,
            "status": status,
            "timestamp": now,
        }
        self._save_event(event)

    def detect(self) -> list[str]:
        """슬라이딩 윈도우 내 이벤트를 분석하여 stuck 패턴을 감지한다.

        3가지 규칙을 독립적으로 검사한다:
            규칙 1: 윈도우 내 모든 이벤트가 failed 상태 (연속 오류).
            규칙 2: 동일 task_id가 3회 이상 failed로 반복 (반복 key).
            규칙 3: running->failed 교대 패턴이 4쌍 이상 (진동 패턴).

        Returns:
            감지된 경고 메시지 목록. 없으면 빈 리스트.
        """
        events = self._load_events()
        if not events:
            return []

        warnings: list[str] = []

        # 규칙 1: 연속 오류 — 윈도우 내 모든 이벤트가 failed
        if len(events) >= self.window_size:
            if all(e.get("status") == "failed" for e in events):
                warnings.append(
                    f"STUCK_RULE1: 최근 {self.window_size}개 이벤트 전부 failed "
                    f"(연속 오류 감지)"
                )

        # 규칙 2: 반복 key — 동일 task_id가 3회 이상 failed
        failed_counter: Counter[str] = Counter(
            e.get("task_id", "")
            for e in events
            if e.get("status") == "failed"
        )
        for tid, count in failed_counter.items():
            if count >= 3:
                warnings.append(
                    f"STUCK_RULE2: task_id={tid} failed {count}회 반복 "
                    f"(반복 키 감지)"
                )

        # 규칙 3: 진동 패턴 — running->failed 교대 쌍이 4회 이상
        alternation_count = 0
        prev_status = ""
        for e in events:
            cur_status = e.get("status", "")
            if prev_status == "running" and cur_status == "failed":
                alternation_count += 1
            prev_status = cur_status

        if alternation_count >= 4:
            warnings.append(
                f"STUCK_RULE3: running->failed 진동 패턴 {alternation_count}회 "
                f"(진동 패턴 감지)"
            )

        return warnings


def check_stuck(work_dir: str, task_id: str, status: str) -> None:
    """stuck 패턴 감지 편의 함수.

    StuckDetector를 생성하고, 이벤트를 기록한 후 감지 결과를
    workflow.log에 WARN으로 기록한다.

    비차단 원칙: 모든 예외를 조용히 흡수한다.

    Args:
        work_dir: 워크플로우 절대 경로. status.json이 위치하는 디렉터리.
        task_id: 태스크 ID (예: 'W01').
        status: 태스크 상태 (예: 'running', 'failed', 'completed').
    """
    try:
        detector = StuckDetector(work_dir)
        detector.record_event(task_id, status)
        warnings = detector.detect()
        for warn_msg in warnings:
            _append_log(work_dir, "WARN", f"stuck_detector: {warn_msg}")
    except Exception:
        # 비차단 원칙: 감지 실패가 워크플로우 흐름에 영향 없음
        pass
