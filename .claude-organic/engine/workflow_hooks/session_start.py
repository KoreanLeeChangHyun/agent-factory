#!/usr/bin/env -S python3 -u
"""Workflow SessionStart hook.

워크플로우 세션 시작 시 status.json 의 active phase 와 hook_fails 잔재를
system context 형태로 stdout 에 inject 한다.

활성화 조건:
  - _WF_SESSION_TYPE=workflow (워크플로우 세션 한정)
  - HOOK_WORKFLOW_ORCHESTRATION=true

inject 내용:
  - 현재 active workflow 의 registryKey, workDir, phase, command
  - 직전 hook_fails 잔재가 있으면 LLM 에 노출 (수동 정정 안내)

advisory only — 워크플로우 phase 전이는 PreToolUse hook 이 흡수.
"""

from __future__ import annotations

import os
import sys

_self_dir = os.path.dirname(os.path.abspath(__file__))
if _self_dir not in sys.path:
    sys.path.insert(0, _self_dir)

from _common import (  # noqa: E402
    current_phase,
    find_active_workflow,
    get_ticket_id_from_env,
    is_orchestration_enabled,
    is_workflow_session,
    pop_hook_fails,
)


def main() -> int:
    if not is_workflow_session():
        return 0
    if not is_orchestration_enabled():
        return 0

    # stdin 은 SessionStart payload — 본 hook 은 사용 안 함
    try:
        sys.stdin.buffer.read()
    except Exception:  # noqa: BLE001
        pass

    ticket_id = get_ticket_id_from_env()
    key, work_dir_abs, status = find_active_workflow(ticket_id)
    if not key or not work_dir_abs:
        return 0

    phase = current_phase(status)
    lines: list[str] = []
    lines.append("<workflow-orchestration-context>")
    lines.append(f"  registryKey: {key}")
    lines.append(f"  workDir: {work_dir_abs}")
    lines.append(f"  phase: {phase}")
    if ticket_id:
        lines.append(f"  ticketNumber: {ticket_id}")
    lines.append(
        "  hook_absorption: ENABLED — flow-update both / flow-step start / "
        "flow-phase / flow-skillmap / flow-update task-start / "
        "flow-update task-status / flow-validate 는 자동 호출됩니다. "
        "오케스트레이터는 INIT (cd \"$(flow-init ... | tail -1)\") + Task × N + "
        "DONE (flow-update status DONE + flow-finish + flow-claude end) 만 호출하세요."
    )

    fails = pop_hook_fails(work_dir_abs)
    if fails:
        lines.append("  hook_fail_residue:")
        for f in fails[-5:]:
            lines.append(
                f"    - phase={f.get('phase')} exit={f.get('exit_code')} "
                f"cmd={f.get('command','')[:120]} stderr={f.get('stderr','')[:120]}"
            )
        lines.append(
            "  → 위 hook_fail 잔재 확인 후 필요 시 wrapper 수동 호출로 수습하세요."
        )

    lines.append("</workflow-orchestration-context>")
    sys.stdout.write("\n".join(lines) + "\n")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
