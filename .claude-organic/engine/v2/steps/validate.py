"""VALIDATE Step — claude -p 1 spawn → validate-report.md (advisory).

driver 룰베이스 12룰 재검증은 done_step 에서 수행 (REPORT 완료 + DONE step.end 기록
후가 정합 시점 — VALIDATE 시점은 report.md / step.end DONE 미생성으로 거짓 FAIL).
"""

from __future__ import annotations

from .. import _verify_code
from .._common import WorkflowContext, append_log, load_prompt, write_context
from .._retry import spawn_with_retry
from .._spawn import logical_session_name, new_session_uuid
from .._verify import verify_validate_md


def validate_step(ctx: WorkflowContext) -> None:
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
    initial_prompt = (
        f"plan.md (통째):\n{plan_body}\n\n"
        f"work/**/*.md (모두 통째):\n{joined_work}\n\n"
        f"**Quality 평가 자연어** 만 (phase 분해 적정성 / deliverable 완성도 / deps 흐름 일관성 / 종합 자연어)\n"
        f"`{ctx.validate_report_md_path()}` 에 작성. **14+룰 평가·verdict 산출·코드 검증(pytest/lint) 금지 (SPEC §0.1)** — "
        f"driver 가 DONE 단계에서 `validate/rules.json` SSOT 결정론 산출 + "
        f"driver `_verify_code.py` 가 본 VALIDATE Step 안에서 `validate/code.json` 산출."
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
    flat_report = ctx.validate_report_md_path()
    if flat_report.exists():
        nested_report = ctx.validate_report_md_nested_path()
        nested_report.parent.mkdir(parents=True, exist_ok=True)
        nested_report.write_text(flat_report.read_text(encoding="utf-8"), encoding="utf-8")
    try:
        _verify_code.run(ctx)
    except Exception as exc:  # noqa: BLE001 — graceful boundary
        append_log(ctx, f"[VALIDATE] _verify_code.run failed: {type(exc).__name__}: {exc}")
