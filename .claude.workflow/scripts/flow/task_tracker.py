"""task_tracker.py - 태스크 상태 관리 모듈.

status.json의 tasks 객체에 대한 태스크 상태(pending, running, completed, failed)를
기록하고 관리하는 책임을 담당한다.

책임 범위:
    - 태스크 상태 기록 (update_task_status)
    - 태스크 상태 유효성 검증
    - 상태별 구조화 로그 기록 (AGENT_DISPATCH, AGENT_RETURN)
"""
from __future__ import annotations

import os
import sys
from datetime import datetime

# scripts 디렉터리를 sys.path에 추가하여 common, data 패키지 import 허용
_scripts_dir: str = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
)
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from common import atomic_write_json, load_json_file
from data.constants import KST
from flow.flow_logger import append_log as _append_log


def update_task_status(status_file: str, task_id: str, task_status: str) -> str:
    """status.json의 tasks 객체에 태스크 상태를 기록한다.

    Args:
        status_file: status.json 파일 경로
        task_id: 태스크 ID (예: 'W01', 'W02')
        task_status: 태스크 상태. 허용값: pending|running|completed|failed.
            in_progress는 running으로 자동 변환.

    Returns:
        처리 결과 문자열. 예: 'task-status -> W01: completed (updated_at: ...)',
        'task-status -> skipped (missing args)', 'task-status -> failed'.
    """
    if not task_id or not task_status:
        print("[WARN] task-status: task_id, status 인자가 필요합니다.", file=sys.stderr)
        return "task-status -> skipped (missing args)"

    STATUS_ALIASES: dict[str, str] = {"in_progress": "running"}
    task_status = STATUS_ALIASES.get(task_status, task_status)
    valid_statuses: set[str] = {"pending", "running", "completed", "failed"}
    if task_status not in valid_statuses:
        print(
            f"[WARN] task-status: status는 pending|running|completed|failed 중 하나여야 합니다. (받은 값: {task_status})",
            file=sys.stderr,
        )
        return "task-status -> skipped (invalid status)"

    if not os.path.exists(status_file):
        print(f"[WARN] status.json not found: {status_file}", file=sys.stderr)
        return "task-status -> skipped (file not found)"

    try:
        data = load_json_file(status_file)
        if data is None:
            return "task-status -> skipped (read failed)"

        if "tasks" not in data or not isinstance(data.get("tasks"), dict):
            data["tasks"] = {}

        kst = KST
        now: str = datetime.now(kst).strftime("%Y-%m-%dT%H:%M:%S+09:00")

        data["tasks"][task_id] = {"status": task_status, "updated_at": now}
        atomic_write_json(status_file, data)

        # 상태별 구조화 로그 기록
        abs_work_dir_log: str = os.path.dirname(status_file)
        if task_status == "running":
            _append_log(abs_work_dir_log, "INFO", f"AGENT_DISPATCH: taskId={task_id}")
        elif task_status in {"completed", "failed"}:
            _append_log(abs_work_dir_log, "INFO", f"AGENT_RETURN: taskId={task_id} status={task_status}")

        return f"task-status -> {task_id}: {task_status} (updated_at: {now})"
    except Exception as e:
        print(f"[WARN] task-status failed: {e}", file=sys.stderr)
        return "task-status -> failed"
