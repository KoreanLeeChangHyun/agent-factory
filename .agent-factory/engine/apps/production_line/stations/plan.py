"""PLAN Step — claude -p 1 spawn → plan/plan.json + plan/plan.md (T-504 cutover)."""

from __future__ import annotations

from .._common import WorkflowContext, load_prompt, write_context
from .._retry import spawn_with_retry
from .._spawn import logical_session_name, new_session_uuid
from .._verify import verify_plan_artifacts


def plan_step(ctx: WorkflowContext) -> None:
    work_request_dump = ctx.user_prompt_path().read_text(encoding="utf-8")
    # T-504 — plan/ directory dictionary mkdir (LLM ensures parent dir when writing these two files).
    ctx.plan_dir().mkdir(parents=True, exist_ok=True)
    initial_prompt = (
        f"WorkRequest prompt: \n {work_request_dump} \n \n"
        f"Break down the tasks in the above WorkRequest into phases and create the following two files simultaneously: \n"
        f"1. `{ctx.plan_json_path()}` — JSON SSOT (driver deterministic parsing target). \n"
        f"2. `{ctx.plan_md_path()}` — Markdown natural language body (WORK/VALIDATE/REPORT for LLM handover). \n"
        f"The schema·phase id·deps·acceptance_criteria of the two files must match."
    )
    session_id = new_session_uuid()
    logical = logical_session_name(ctx.work_request_no, "PLAN")
    ctx.session_ids[logical] = session_id
    write_context(ctx)
    spawn_with_retry(
        ctx,
        step="PLAN",
        initial_prompt=initial_prompt,
        system_prompt=load_prompt("plan"),
        session_id=session_id,
        verify=lambda: verify_plan_artifacts(
            ctx.plan_json_path(),
            ctx.plan_md_path(),
        ),
        artifact_path=ctx.plan_json_path(),
    )
