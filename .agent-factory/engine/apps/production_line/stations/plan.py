"""PLAN Step — claude -p 1 spawn → plan/plan.json + plan/plan.md (T-504 cutover)."""

from __future__ import annotations

from .._common import WorkflowContext, load_prompt, write_context
from .._retry import spawn_with_retry
from .._spawn import logical_session_name, new_session_uuid
from .._verify import verify_plan_artifacts


def plan_step(ctx: WorkflowContext) -> None:
    ticket_dump = ctx.user_prompt_path().read_text(encoding="utf-8")
    # T-504 — plan/ 디렉터리 사전 mkdir (LLM 이 두 파일 Write 시 부모 dir 보장).
    ctx.plan_dir().mkdir(parents=True, exist_ok=True)
    initial_prompt = (
        f"티켓 prompt:\n{ticket_dump}\n\n"
        f"위 티켓의 작업을 phase 단위로 분해해 다음 두 파일을 동시 작성하세요:\n"
        f"1. `{ctx.plan_json_path()}` — JSON SSOT (driver 결정론 파싱 대상).\n"
        f"2. `{ctx.plan_md_path()}` — Markdown 자연어 본문 (WORK/VALIDATE/REPORT LLM 인계용).\n"
        f"두 파일은 schema·phase id·deps·acceptance_criteria 가 정합해야 합니다."
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
        verify=lambda: verify_plan_artifacts(
            ctx.plan_json_path(),
            ctx.plan_md_path(),
        ),
        artifact_path=ctx.plan_json_path(),
    )
