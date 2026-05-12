#!/usr/bin/env -S python3 -u
"""Workflow PreToolUse[Task] hook.

Task 도구 호출 직전 subagent_type 에 따라 결정론 단계 wrapper 를 자동 실행한다.

흡수 대상 wrapper:
  planner            : flow-update both <key> planner PLAN + flow-step start <key>
  worker-*/explorer-*: 첫 진입 시 flow-update both <key> worker WORK + flow-step start <key>
                       + flow-phase <key> 0 + flow-skillmap <key>
                       그 다음 (Task prompt 의 phase/taskId 기준)
                       flow-phase <key> <N> + flow-update task-start <key> <taskId>
  validator          : flow-phase <key> <N+1> + flow-update task-start <key> validator
  reporter           : flow-update both <key> reporter REPORT + flow-step start <key>

advisory only — wrapper 실패 시 hook_fail 잔재 기록 후 PreToolUse allow 출력.
실패는 다음 SessionStart hook 또는 사용자 수동 정정으로 회복.

활성화 조건:
  - tool_name == 'Task' && subagent_type ∈ workflow set
  - _WF_SESSION_TYPE=workflow (또는 _WF_TICKET_ID 매칭)
  - HOOK_WORKFLOW_ORCHESTRATION=true
"""

from __future__ import annotations

import json
import sys

import os
_self_dir = os.path.dirname(os.path.abspath(__file__))
if _self_dir not in sys.path:
    sys.path.insert(0, _self_dir)

from _common import (  # noqa: E402
    ALLOWED_SUBAGENT_TYPES,
    WORKER_SUBAGENT_TYPES,
    TERMINAL_PHASES_LOCAL,
    bin_path,
    current_phase,
    emit_allow,
    extract_subagent_type,
    extract_task_meta,
    find_active_workflow,
    get_ticket_id_from_env,
    is_orchestration_enabled,
    is_workflow_session,
    log_workflow_event,
    mark_phase_zero_done,
    phase_zero_done,
    run_wrapper,
)


def _handle_planner(key: str, work_dir_abs: str, phase: str) -> None:
    if phase in ("NONE", "INIT", "STALE", "FAILED", "PLAN"):
        run_wrapper([bin_path("flow-update"), "both", key, "planner", "PLAN"], work_dir_abs, "PLAN")
        run_wrapper([bin_path("flow-step"), "start", key], work_dir_abs, "PLAN")
        log_workflow_event(work_dir_abs, "HOOK[Pre,Task=planner] PLAN 자동 전이 (flow-update both + flow-step start)")


def _handle_worker(key: str, work_dir_abs: str, status: dict, meta: dict) -> None:
    phase = current_phase(status)
    if phase in ("PLAN", "NONE", "INIT"):
        run_wrapper([bin_path("flow-update"), "both", key, "worker", "WORK"], work_dir_abs, "WORK")
        run_wrapper([bin_path("flow-step"), "start", key], work_dir_abs, "WORK")
        log_workflow_event(work_dir_abs, "HOOK[Pre,Task=worker] WORK 자동 전이")

    if not phase_zero_done(status):
        run_wrapper([bin_path("flow-phase"), key, "0"], work_dir_abs, "WORK")
        run_wrapper([bin_path("flow-skillmap"), key], work_dir_abs, "WORK")
        status_path = os.path.join(work_dir_abs, "status.json")
        mark_phase_zero_done(status_path)
        log_workflow_event(work_dir_abs, "HOOK[Pre,Task=worker] Phase 0 + skillmap 자동 실행")

    task_id = meta.get("taskId", "")
    phase_n = meta.get("phase", "")
    if phase_n:
        run_wrapper([bin_path("flow-phase"), key, str(phase_n)], work_dir_abs, "WORK")
    if task_id:
        run_wrapper([bin_path("flow-update"), "task-start", key, task_id], work_dir_abs, "WORK")
        log_workflow_event(work_dir_abs, f"HOOK[Pre,Task=worker] phase={phase_n} task-start={task_id}")


def _handle_validator(key: str, work_dir_abs: str, status: dict, meta: dict) -> None:
    phase_n = meta.get("phase", "")
    if not phase_n:
        worker_count = 0
        tasks = status.get("tasks", {}) if isinstance(status, dict) else {}
        for tid in tasks.keys():
            if tid.startswith("W"):
                worker_count += 1
        phase_n = str(max(worker_count + 1, 1))

    run_wrapper([bin_path("flow-phase"), key, str(phase_n)], work_dir_abs, "WORK")
    run_wrapper([bin_path("flow-update"), "task-start", key, "validator"], work_dir_abs, "WORK")
    log_workflow_event(work_dir_abs, f"HOOK[Pre,Task=validator] phase={phase_n} task-start=validator")


def _handle_reporter(key: str, work_dir_abs: str, phase: str) -> None:
    run_wrapper([bin_path("flow-update"), "both", key, "reporter", "REPORT"], work_dir_abs, "REPORT")
    run_wrapper([bin_path("flow-step"), "start", key], work_dir_abs, "REPORT")
    log_workflow_event(work_dir_abs, "HOOK[Pre,Task=reporter] REPORT 자동 전이")


def main() -> int:
    if not is_orchestration_enabled():
        emit_allow("HOOK_WORKFLOW_ORCHESTRATION 비활성 — 통과.")
        return 0

    if not is_workflow_session():
        emit_allow("워크플로우 세션 아님 — 통과 (메인 세션 hook 사이드 이펙트 차단).")
        return 0

    try:
        payload = json.loads(sys.stdin.buffer.read())
    except (json.JSONDecodeError, ValueError):
        emit_allow("payload 파싱 실패 — 통과.")
        return 0

    tool_name = payload.get("tool_name", "")
    if tool_name != "Task":
        emit_allow("Task 도구 아님 — 통과.")
        return 0

    tool_input = payload.get("tool_input", {}) or {}
    subagent_type = extract_subagent_type(tool_input)
    if subagent_type not in ALLOWED_SUBAGENT_TYPES:
        emit_allow(f"subagent_type={subagent_type!r} 워크플로우 set 밖 — 통과.")
        return 0

    ticket_id = get_ticket_id_from_env()
    key, work_dir_abs, status = find_active_workflow(ticket_id)
    if not key or not work_dir_abs:
        emit_allow("active workflow 미탐지 — 통과.")
        return 0

    phase = current_phase(status)
    if phase in TERMINAL_PHASES_LOCAL:
        emit_allow(f"phase={phase} 종착 상태 — 통과.")
        return 0

    prompt = tool_input.get("prompt", "")
    meta = extract_task_meta(prompt if isinstance(prompt, str) else "")

    try:
        if subagent_type == "planner":
            _handle_planner(key, work_dir_abs, phase)
        elif subagent_type in WORKER_SUBAGENT_TYPES:
            _handle_worker(key, work_dir_abs, status, meta)
        elif subagent_type == "validator":
            _handle_validator(key, work_dir_abs, status, meta)
        elif subagent_type == "reporter":
            _handle_reporter(key, work_dir_abs, phase)
    except Exception as e:  # noqa: BLE001
        log_workflow_event(work_dir_abs, f"HOOK[Pre,Task] exception: {e}")

    emit_allow(f"워크플로우 결정론 단계 자동 실행 완료 (subagent={subagent_type}, phase={phase}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
