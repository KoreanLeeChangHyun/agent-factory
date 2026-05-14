"""INIT Step — driver in-process. LLM 호출 없음."""

from __future__ import annotations

import sys

from .._common import (
    WorkflowContext,
    append_log,
    kanban_move,
    kanban_show,
    make_work_dir,
    new_registry_key,
    update_step,
    write_context,
    write_status,
)
from .._emitter import step_end, step_start


def init_step(ticket_no: str) -> WorkflowContext:
    """INIT — kanban Open→In Progress, work_dir + 초기 status.json.

    ticket 존재 가드: kanban_show 결과 'Number:' 토큰 없으면 SystemExit(2).
    """
    registry_key = new_registry_key()
    work_dir = make_work_dir(registry_key)
    ctx = WorkflowContext(
        ticket_no=ticket_no,
        registry_key=registry_key,
        work_dir=work_dir,
        command="implement",
        mode="multi",
        current_step="INIT",
    )
    ticket_dump = kanban_show(ticket_no)
    if not ticket_dump or "Number:" not in ticket_dump:
        sys.stderr.write(
            f"[driver] ticket {ticket_no} not found in kanban — aborting INIT\n"
        )
        raise SystemExit(2)
    ctx.user_prompt_path().write_text(ticket_dump, encoding="utf-8")
    write_status(ctx, {"workflow_step": "INIT", "transitions": []})
    write_context(ctx)
    append_log(ctx, f"INIT — registry_key={registry_key}, ticket={ticket_no}")
    step_start(ctx, "INIT")
    kanban_move(ticket_no, "progress")
    step_end(ctx, "INIT", outcome="ok")
    update_step(ctx, "INIT", "PLAN")
    return ctx
