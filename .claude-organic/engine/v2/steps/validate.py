"""VALIDATE Step — claude -p 1 spawn → validate-report.md (advisory)."""

from __future__ import annotations

from .._common import WorkflowContext, load_prompt, write_context
from .._retry import spawn_with_retry
from .._spawn import logical_session_name, new_session_uuid
from .._verify import verify_validate_md


def validate_step(ctx: WorkflowContext) -> None:
    plan_body = ctx.plan_md_path().read_text(encoding="utf-8")
    work_blocks: list[str] = []
    work_dir = ctx.work_dir / "work"
    if work_dir.exists():
        for md in sorted(work_dir.glob("*.md")):
            work_blocks.append(
                f"### work/{md.name}\n\n{md.read_text(encoding='utf-8')}\n"
            )
    joined_work = "\n".join(work_blocks) if work_blocks else "(work/ 비어있음)"
    initial_prompt = (
        f"plan.md (통째):\n{plan_body}\n\n"
        f"work/*.md (모두 통째):\n{joined_work}\n\n"
        f"12 룰 advisory 평가 + 추가 quality 검증을 `{ctx.validate_report_md_path()}` 에 작성."
    )
    session_id = new_session_uuid()
    logical = logical_session_name(ctx.ticket_no, "VALIDATE")
    ctx.session_ids[logical] = session_id
    write_context(ctx)
    spawn_with_retry(
        ctx,
        step="VALIDATE",
        initial_prompt=initial_prompt,
        system_prompt=load_prompt("validate"),
        session_id=session_id,
        verify=lambda: verify_validate_md(ctx.validate_report_md_path()),
        artifact_path=ctx.validate_report_md_path(),
    )
