"""REPORT Step — claude -p 1 spawn → report.md (plan + work + validate 통째 inject)."""

from __future__ import annotations

from .._common import WorkflowContext, load_prompt, write_context
from .._retry import spawn_with_retry
from .._spawn import logical_session_name, new_session_uuid
from .._verify import verify_report_md


def report_step(ctx: WorkflowContext) -> None:
    plan_body = ctx.plan_md_path().read_text(encoding="utf-8")
    work_blocks: list[str] = []
    work_dir = ctx.work_dir / "work"
    if work_dir.exists():
        for md in sorted(work_dir.glob("**/*.md")):
            rel = md.relative_to(work_dir)
            work_blocks.append(
                f"### work/{rel.as_posix()}\n\n{md.read_text(encoding='utf-8')}\n"
            )
    joined_work = "\n".join(work_blocks) if work_blocks else "(work/ 비어있음)"
    validate_body = (
        ctx.validate_report_md_path().read_text(encoding="utf-8")
        if ctx.validate_report_md_path().exists()
        else ""
    )
    initial_prompt = (
        f"plan.md:\n{plan_body}\n\n"
        f"work/**/*.md:\n{joined_work}\n\n"
        f"validate-report.md (LLM Quality 평가 자연어):\n{validate_body}\n\n"
        f"위를 통째 종합한 report.md 를 `{ctx.report_md_path()}` 에 작성. "
        f"본문에 'plan.md' 토큰 포함 필수. "
        f"**14+룰 verdict (PASS/WARN/FAIL/SKIP) 산출·재평가·코드 검증(pytest/lint) 금지 (SPEC §0.1)** — "
        f"driver 가 DONE 단계에서 `validate/rules.json` SSOT 결정론 산출 + "
        f"VALIDATE 단계에서 `validate/code.json` 산출. "
        f"필요 시 '14+룰 verdict 는 driver validate/rules.json 참조' 1줄 안내만."
    )
    session_id = new_session_uuid()
    logical = logical_session_name(ctx.ticket_no, "REPORT")
    ctx.session_ids[logical] = session_id
    write_context(ctx)
    spawn_with_retry(
        ctx,
        step="REPORT",
        initial_prompt=initial_prompt,
        system_prompt=load_prompt("report"),
        session_id=session_id,
        verify=lambda: verify_report_md(ctx.report_md_path(), ctx.plan_md_path()),
        artifact_path=ctx.report_md_path(),
    )
