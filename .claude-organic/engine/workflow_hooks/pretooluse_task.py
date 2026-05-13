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
import time

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
    emit_deny,
    extract_subagent_type,
    extract_task_meta,
    find_active_workflow,
    format_hook_fail_alert,
    get_ticket_id_from_env,
    is_orchestration_enabled,
    is_workflow_session,
    log_workflow_event,
    mark_phase_zero_done,
    phase_zero_done,
    pop_hook_fails,
    project_root,
    run_wrapper,
)


_PHASE_ORDER = ["NONE", "INIT", "PLAN", "WORK", "VALIDATE", "REPORT", "DONE"]


def _ensure_phase_reached(key: str, work_dir_abs: str, current: str, target: str) -> None:
    """current 단계부터 target 직전 단계까지 FSM 룰에 따라 순차 전이를 보장한다.

    FSM_TRANSITIONS[multi]: NONE→INIT→PLAN→WORK→VALIDATE→REPORT→DONE.
    target 단계 자체 전이는 호출자(_handle_*)가 처리한다.
    """
    try:
        cur_idx = _PHASE_ORDER.index(current)
        tgt_idx = _PHASE_ORDER.index(target)
    except ValueError:
        return
    if cur_idx >= tgt_idx:
        return
    for i in range(cur_idx + 1, tgt_idx):
        prev = _PHASE_ORDER[i - 1]
        phase = _PHASE_ORDER[i]
        run_wrapper([bin_path("flow-update"), "both", key, "orchestrator", phase], work_dir_abs, phase)
        log_workflow_event(work_dir_abs, f"HOOK[Pre,Task] {prev}→{phase} 사전 전이 (FSM 순차 보장)")


def _trace_hook_entry(payload: dict) -> None:
    """본 hook 진입 시 env 값 + payload 요약을 외부 디버그 파일에 기록한다.

    가설 2 진단용 (T-483): 실제 워크플로우 발사 시 hook 호출 여부와
    `_WF_SESSION_TYPE`/`_WF_TICKET_ID` env 도달 여부 검증을 위한 영구 trace.
    파일: .claude-organic/runs/bg/hook-trace.log
    """
    try:
        trace_path = os.path.join(project_root(), ".claude-organic", "runs", "bg", "hook-trace.log")
        os.makedirs(os.path.dirname(trace_path), exist_ok=True)
        ts = time.strftime("%Y-%m-%dT%H:%M:%S")
        wf_session = os.environ.get("_WF_SESSION_TYPE", "")
        wf_ticket = os.environ.get("_WF_TICKET_ID", "")
        wf_session_id = os.environ.get("_WF_SESSION_ID", "")
        tool_name = payload.get("tool_name", "?") if isinstance(payload, dict) else "?"
        tool_input = payload.get("tool_input", {}) if isinstance(payload, dict) else {}
        sat = tool_input.get("subagent_type", "?") if isinstance(tool_input, dict) else "?"
        with open(trace_path, "a", encoding="utf-8") as f:
            f.write(
                f"[{ts}] tool={tool_name} subagent={sat} "
                f"_WF_SESSION_TYPE={wf_session!r} _WF_TICKET_ID={wf_ticket!r} "
                f"_WF_SESSION_ID={wf_session_id!r}\n"
            )
    except Exception:  # noqa: BLE001
        pass


def _handle_planner(key: str, work_dir_abs: str, phase: str) -> None:
    if phase in ("NONE", "INIT", "STALE", "FAILED", "PLAN"):
        _ensure_phase_reached(key, work_dir_abs, phase, "PLAN")
        run_wrapper([bin_path("flow-update"), "both", key, "planner", "PLAN"], work_dir_abs, "PLAN")
        run_wrapper([bin_path("flow-step"), "start", key], work_dir_abs, "PLAN")
        log_workflow_event(work_dir_abs, "HOOK[Pre,Task=planner] PLAN 자동 전이 (flow-update both + flow-step start)")


def _handle_worker(key: str, work_dir_abs: str, status: dict, meta: dict) -> None:
    phase = current_phase(status)
    if phase in ("PLAN", "NONE", "INIT"):
        _ensure_phase_reached(key, work_dir_abs, phase, "WORK")
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
    phase = current_phase(status)
    _ensure_phase_reached(key, work_dir_abs, phase, "VALIDATE")
    run_wrapper([bin_path("flow-update"), "both", key, "validator", "VALIDATE"], work_dir_abs, "VALIDATE")

    phase_n = meta.get("phase", "")
    if not phase_n:
        worker_count = 0
        tasks = status.get("tasks", {}) if isinstance(status, dict) else {}
        for tid in tasks.keys():
            if tid.startswith("W"):
                worker_count += 1
        phase_n = str(max(worker_count + 1, 1))

    run_wrapper([bin_path("flow-phase"), key, str(phase_n)], work_dir_abs, "VALIDATE")
    run_wrapper([bin_path("flow-update"), "task-start", key, "validator"], work_dir_abs, "VALIDATE")
    log_workflow_event(work_dir_abs, f"HOOK[Pre,Task=validator] phase={phase_n} task-start=validator")


def _handle_reporter(key: str, work_dir_abs: str, phase: str) -> None:
    _ensure_phase_reached(key, work_dir_abs, phase, "REPORT")
    run_wrapper([bin_path("flow-update"), "both", key, "reporter", "REPORT"], work_dir_abs, "REPORT")
    run_wrapper([bin_path("flow-step"), "start", key], work_dir_abs, "REPORT")
    log_workflow_event(work_dir_abs, "HOOK[Pre,Task=reporter] REPORT 자동 전이")


def main() -> int:
    # stdin payload 파싱을 게이트 앞에 둔다 — 디버그 trace 가 payload 요약을 포함하기 위함.
    try:
        payload = json.loads(sys.stdin.buffer.read())
    except (json.JSONDecodeError, ValueError):
        _trace_hook_entry({})
        emit_allow("payload 파싱 실패 — 통과.")
        return 0

    # 가설 2 진단용 영구 trace — hook 호출 + env 도달 여부 검증 (T-483).
    _trace_hook_entry(payload)

    if not is_orchestration_enabled():
        emit_allow("HOOK_WORKFLOW_ORCHESTRATION 비활성 — 통과.")
        return 0

    if not is_workflow_session():
        emit_allow("워크플로우 세션 아님 — 통과 (메인 세션 hook 사이드 이펙트 차단).")
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

    # hook_fails 잔재 즉시 가시화 (약점 4축 #1, T-483):
    # 직전 PreToolUse/PostToolUse hook 에서 wrapper 호출이 실패했으면
    # 본 PreToolUse 가 deny 1회 발화 + 잔재 비움. LLM 은 deny reason 으로
    # 즉시 인지 → 재시도 시 잔재 빈 상태이므로 정상 진행.
    fails = pop_hook_fails(work_dir_abs)
    if fails:
        log_workflow_event(
            work_dir_abs,
            f"HOOK[Pre,Task={subagent_type}] hook_fails 잔재 {len(fails)}건 deny 통보 (1회)",
        )
        emit_deny(format_hook_fail_alert(fails))
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
