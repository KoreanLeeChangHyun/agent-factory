"""task tracker.py - task status management module.

execute, execute, completed, failed
We are responsible for record and management.

Payment Terms:
    - Task Status Record (update task status)
    - Validation of task status
    (AGENT DISPATCH, AGENT RETURN)
"""
from __future__ import annotations

import os
import sys
from collections import Counter
from datetime import datetime

# Add the scripts directory to sys.path to allow import of common and data packages
_engine_dir: str = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
)
if _engine_dir not in sys.path:
    sys.path.insert(0, _engine_dir)

from common import atomic_write_json, load_json_file
from constants import KST
from flow.flow_logger import append_log as _append_log


def update_task_status(status_file: str, task_id: str, task_status: str) -> str:
    """status.json's task object writes the task status.

    Args:
        status file: status.json file path
        task id: task ID (e.g. 'W01', 'W02')
        task status: task status. pending running completed failed.
            in progress automatically converts to running.

    Returns:
        The resulting string. Example: 'task-status -> W01: completed (updated at: ...)',
        'task-status -> skipped (missing args)', 'task-status -> failed'.
    """
    if not task_id or not task_status:
        print("[WARN] task-status: task_id and status arguments are required.", file=sys.stderr)
        return "task-status -> skipped (missing args)"

    STATUS_ALIASES: dict[str, str] = {"in_progress": "running"}
    task_status = STATUS_ALIASES.get(task_status, task_status)
    valid_statuses: set[str] = {"pending", "running", "completed", "failed"}
    if task_status not in valid_statuses:
        print(
            f"[WARN] task-status: status must be one of pending|running|completed|failed. (Value received: {task_status})",
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

        # Structured log records by status
        abs_work_dir_log: str = os.path.dirname(status_file)
        if task_status == "running":
            _append_log(abs_work_dir_log, "INFO", f"AGENT_DISPATCH: taskId={task_id}")
        elif task_status in {"completed", "failed"}:
            _append_log(abs_work_dir_log, "INFO", f"AGENT_RETURN: taskId={task_id} status={task_status}")

        # P07: Stuck pattern detection (non-blocking principle)
        try:
            _check_stuck(abs_work_dir_log, task_id, task_status)
        except Exception:
            pass

        return f"task-status -> {task_id}: {task_status} (updated_at: {now})"
    except Exception as e:
        print(f"[WARN] task-status failed: {e}", file=sys.stderr)
        return "task-status -> failed"




class StuckDetector:
    """Sliding window-based stuck pattern sensor.

    status.json's task events array,
    The window size event is analyzed and detects the stuck pattern.

    Attributes:
        work dir: Workflow absolute path (status.json location).
        window size: sliding window size (default 6).
    """

    def __init__(self, work_dir: str, window_size: int = 6) -> None:
        """StuckDetector initialization.

        Args:
            work dir: workflow absolute path. directory where status.json is located.
            window size: sliding window size. Use only N events.
        """
        self.work_dir = work_dir
        self.window_size = window_size
        self._status_file = os.path.join(work_dir, "status.json")

    def _load_events(self) -> list[dict]:
        """loads recent window size events in status.json's task events array.

        Returns:
            Recent Window size Event Dixie List.
            return empty list without status.json or if there is no task events field.
        """
        data = load_json_file(self._status_file)
        if not isinstance(data, dict):
            return []
        events = data.get("task_events", [])
        if not isinstance(events, list):
            return []
        return events[-self.window_size:]

    def _save_event(self, event: dict) -> None:
        """add event to the task events array in status.json.

        Window size * 2 or more
        Cut out old events (Minimum of memory / disk burden).

        Args:
            event: Event Dixie to record. {task id, status, timestamp} structure.
        """
        if not os.path.exists(self._status_file):
            return

        data = load_json_file(self._status_file)
        if not isinstance(data, dict):
            return

        if "task_events" not in data or not isinstance(data.get("task_events"), list):
            data["task_events"] = []

        data["task_events"].append(event)

        # Clean up old events: if window_size * 2 is exceeded, truncate from the front.
        max_keep = self.window_size * 2
        if len(data["task_events"]) > max_keep:
            data["task_events"] = data["task_events"][-max_keep:]

        atomic_write_json(self._status_file, data)

    def record_event(self, task_id: str, status: str) -> None:
        """The task event is recorded in status.json.

        Args:
            task id: task ID (e.g. 'W01', 'W02').
            status: "running", "failed", "completed"
        """
        now: str = datetime.now(KST).strftime("%Y-%m-%dT%H:%M:%S+09:00")
        event = {
            "task_id": task_id,
            "status": status,
            "timestamp": now,
        }
        self._save_event(event)

    def detect(self) -> list[str]:
        """This window will automatically close when payment is processed.

        3 rules independently checked NEWS
            Rule 1: All events in Windows failed status (continuous errors).
            Rule 2: Repeat the same task id to 3 times failed (back key).
            Rule 3: Running->failed shift patterns over 4 pairs (vibration patterns).

        Returns:
            List of detected alert messages. Without empty list.
        """
        events = self._load_events()
        if not events:
            return []

        warnings: list[str] = []

        # Rule 1: Consecutive errors — all events in the window failed
        if len(events) >= self.window_size:
            if all(e.get("status") == "failed" for e in events):
                warnings.append(
                    f"STUCK_RULE1: All recent {self.window_size} events failed"
                    f"(Continuous error detection)"
                )

        # Rule 2: Repeat key — same task_id failed more than 3 times
        failed_counter: Counter[str] = Counter(
            e.get("task_id", "")
            for e in events
            if e.get("status") == "failed"
        )
        for tid, count in failed_counter.items():
            if count >= 3:
                warnings.append(
                    f"STUCK_RULE2: task_id={tid} failed Repeat {count} times"
                    f"(repeated key detection)"
                )

        # Rule 3: Oscillation pattern — running->failed alternating pairs 4 or more times
        alternation_count = 0
        prev_status = ""
        for e in events:
            cur_status = e.get("status", "")
            if prev_status == "running" and cur_status == "failed":
                alternation_count += 1
            prev_status = cur_status

        if alternation_count >= 4:
            warnings.append(
                f"STUCK_RULE3: running->failed vibration pattern {alternation_count} times"
                f"(Vibration pattern detection)"
            )

        return warnings


def check_stuck(work_dir: str, task_id: str, status: str) -> None:
    """Convenience function to detect the stuck pattern.

    Create StuckDetector and record events and detect results
    write to WARN in workflow.log.

    Non-blocking principles: Quietly absorb all exceptions.

    Args:
        work dir: workflow absolute path. directory where status.json is located.
        task id: task ID (e.g. 'W01').
        status: "running", "failed", "completed"
    """
    try:
        detector = StuckDetector(work_dir)
        detector.record_event(task_id, status)
        warnings = detector.detect()
        for warn_msg in warnings:
            _append_log(work_dir, "WARN", f"stuck_detector: {warn_msg}")
    except Exception:
        # Non-blocking principle: Detection failures have no impact on workflow flow
        pass


_check_stuck = check_stuck  # Caller (line 84) compatible alias
