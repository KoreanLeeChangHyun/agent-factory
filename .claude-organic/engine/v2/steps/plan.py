"""PLAN Step — claude -p 1 spawn → plan.md."""

from __future__ import annotations

from .._common import WorkflowContext, load_prompt, write_context
from .._retry import spawn_with_retry
from .._spawn import logical_session_name, new_session_uuid
from .._verify import verify_plan_md


def plan_step(ctx: WorkflowContext) -> None:
    ticket_dump = ctx.user_prompt_path().read_text(encoding="utf-8")
    initial_prompt = (
        f"티켓 prompt:\n{ticket_dump}\n\n"
        f"위 티켓의 작업을 phase 단위로 분해해 plan.md (frontmatter + body) 를 "
        f"`{ctx.plan_md_path()}` 에 작성하세요."
    )
    session_id = new_session_uuid()
    logical = logical_session_name(ctx.ticket_no, "PLAN")
    ctx.session_ids[logical] = session_id
    write_context(ctx)
    spawn_with_retry(
        ctx,
        step="PLAN",
        initial_prompt=initial_prompt,
        system_prompt=load_prompt("plan"),
        session_id=session_id,
        verify=lambda: verify_plan_md(ctx.plan_md_path()),
        artifact_path=ctx.plan_md_path(),
    )
