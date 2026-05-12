#!/usr/bin/env -S python3 -u
"""Workflow PostToolUse[Task] hook.

Task 도구 반환 직후 subagent_type 에 따라 결정론 wrapper 를 자동 실행한다.

흡수 대상 wrapper:
  planner            : flow-validate <workDir>/plan.md (advisory)
  worker-*/explorer-*: flow-update task-status <key> <taskId> completed|failed
  validator          : flow-update task-status <key> validator completed|failed
                       (작업내역 전체 누락 hard-fail 은 wrapper 결과로만 advisory 기록)
  reporter           : 별도 wrapper 없음 — 오케스트레이터가 명시 호출
                       (flow-update status DONE + flow-finish + flow-claude end)

비차단 fire-and-forget. 본 hook 은 exit 0 고정.

활성화 조건:
  - tool_name == 'Task' && subagent_type ∈ workflow set
  - HOOK_WORKFLOW_ORCHESTRATION=true
"""

from __future__ import annotations

import json
import os
import sys

_self_dir = os.path.dirname(os.path.abspath(__file__))
if _self_dir not in sys.path:
    sys.path.insert(0, _self_dir)

from _common import (  # noqa: E402
    ALLOWED_SUBAGENT_TYPES,
    WORKER_SUBAGENT_TYPES,
    TERMINAL_PHASES_LOCAL,
    bin_path,
    current_phase,
    extract_subagent_type,
    extract_task_meta,
    find_active_workflow,
    get_ticket_id_from_env,
    is_orchestration_enabled,
    is_workflow_session,
    log_workflow_event,
    run_wrapper,
)


def _detect_outcome(tool_result: object) -> str:
    """tool_result 에서 worker 반환 상태를 추론한다. 기본 completed."""
    try:
        if tool_result is None:
            return "completed"
        text = tool_result if isinstance(tool_result, str) else json.dumps(tool_result, ensure_ascii=False)
        head = text[:600].lower()
        if "상태: 실패" in text or "\"status\": \"failed\"" in head or "exception" in head:
            return "failed"
        return "completed"
    except Exception:  # noqa: BLE001
        return "completed"


def main() -> int:
    if not is_orchestration_enabled():
        return 0

    if not is_workflow_session():
        return 0

    try:
        payload = json.loads(sys.stdin.buffer.read())
    except (json.JSONDecodeError, ValueError):
        return 0

    tool_name = payload.get("tool_name", "")
    if tool_name != "Task":
        return 0

    tool_input = payload.get("tool_input", {}) or {}
    subagent_type = extract_subagent_type(tool_input)
    if subagent_type not in ALLOWED_SUBAGENT_TYPES:
        return 0

    ticket_id = get_ticket_id_from_env()
    key, work_dir_abs, status = find_active_workflow(ticket_id)
    if not key or not work_dir_abs:
        return 0

    phase = current_phase(status)
    if phase in TERMINAL_PHASES_LOCAL:
        return 0

    tool_result = payload.get("tool_result")
    outcome = _detect_outcome(tool_result)
    prompt = tool_input.get("prompt", "")
    meta = extract_task_meta(prompt if isinstance(prompt, str) else "")

    try:
        if subagent_type == "planner":
            plan_path = os.path.join(work_dir_abs, "plan.md")
            if os.path.isfile(plan_path):
                run_wrapper([bin_path("flow-validate"), plan_path], work_dir_abs, "PLAN")
                log_workflow_event(work_dir_abs, "HOOK[Post,Task=planner] flow-validate 자동 호출 (advisory)")

        elif subagent_type in WORKER_SUBAGENT_TYPES:
            task_id = meta.get("taskId", "")
            if task_id:
                run_wrapper(
                    [bin_path("flow-update"), "task-status", key, task_id, outcome],
                    work_dir_abs,
                    "WORK",
                )
                log_workflow_event(
                    work_dir_abs,
                    f"HOOK[Post,Task=worker] task-status {task_id} -> {outcome}",
                )

        elif subagent_type == "validator":
            run_wrapper(
                [bin_path("flow-update"), "task-status", key, "validator", outcome],
                work_dir_abs,
                "WORK",
            )
            log_workflow_event(
                work_dir_abs,
                f"HOOK[Post,Task=validator] task-status validator -> {outcome}",
            )

    except Exception as e:  # noqa: BLE001
        log_workflow_event(work_dir_abs, f"HOOK[Post,Task] exception: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
