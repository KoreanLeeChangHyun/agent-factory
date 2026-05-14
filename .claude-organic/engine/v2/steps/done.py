"""DONE / FAILED Step — driver in-process. LLM 호출 없음."""

from __future__ import annotations

from datetime import datetime

from .._common import WorkflowContext, kanban_move, load_template, update_step
from .._emitter import emit, regression, step_end, step_start, workflow_finish
from .._validate import evaluate_12_rules, save_verdict_report


def done_step(ctx: WorkflowContext) -> None:
    """DONE — summary.txt + usage.json + driver 룰베이스 12룰 재검증 + kanban move review.

    SPEC.md §7.1 매핑 표 의 'driver 룰베이스 재검증' 은 본 단계에서 수행 — REPORT
    완료 + step.end DONE 기록 후가 정합 시점. update_step(_, "DONE") 은 main 의
    update_step("REPORT", "DONE") 가 이미 수행하므로 본 함수는 중복 호출하지 않음.
    """
    step_start(ctx, "DONE")
    summary_text = load_template("summary.txt").format(
        ticket_no=ctx.ticket_no,
        registry_key=ctx.registry_key,
        command=ctx.command,
        mode=ctx.mode,
        finalized_at=datetime.now().isoformat(timespec="seconds"),
    )
    ctx.summary_txt_path().write_text(summary_text, encoding="utf-8")
    ctx.usage_json_path().write_text("{}\n", encoding="utf-8")
    step_end(ctx, "DONE", outcome="ok")
    # 12룰 재검증 (REPORT 완료 + step.end DONE 기록 후 — workflow_step 이미 DONE)
    verdict_report = evaluate_12_rules(ctx)
    save_verdict_report(ctx, verdict_report)
    emit(
        ctx,
        "validate.verdict",
        verdict=verdict_report.verdict,
        violation_count=verdict_report.violation_count(),
        has_hard_fail=verdict_report.has_hard_fail(),
        ticket=ctx.ticket_no,
    )
    workflow_finish(ctx, outcome="ok", verdict=verdict_report.verdict)
    kanban_move(ctx.ticket_no, "review")


def fail_step(ctx: WorkflowContext, reason: str) -> None:
    """FAILED — failure.md + kanban 자동 회귀 X (SPEC.md §12.4)."""
    failure_body = load_template("failure.md").format(
        ticket_no=ctx.ticket_no,
        registry_key=ctx.registry_key,
        reason=reason,
        ts=datetime.now().isoformat(timespec="seconds"),
    )
    ctx.failure_md_path().write_text(failure_body, encoding="utf-8")
    regression(ctx, "workflow_step_failed", reason=reason)
    workflow_finish(ctx, outcome="fail", verdict="FAIL")
    update_step(ctx, ctx.current_step, "FAILED", note=reason)
