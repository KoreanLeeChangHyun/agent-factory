"""DONE / FAILED Step — driver in-process. No LLM calls."""

from __future__ import annotations

from datetime import datetime

from .._common import (
    WorkflowContext,
    conveyor_move,
    load_template,
    update_step,
    write_metadata,
)
from .._emitter import emit, regression, step_end, step_start, workflow_finish
from .._validate import evaluate_12_rules, save_verdict_report
from .._verdict import build_final_verdict, save_final_verdict


def done_step(ctx: WorkflowContext) -> None:
    """DONE — summary.txt + usage.json + metadata.json + driver 14+ rule re-verification + conveyor move Verifying.

    ‘Driver rule base revalidation’ in SPEC.md §7.1 mapping table is performed in this step — REPORT
    Finish + step.end DONE Registration point after recording. update_step(_, "DONE") in main
    Since update_step("REPORT", "DONE") has already been performed, this function is not called repeatedly.
    """
    step_start(ctx, "DONE")
    finalized_at = datetime.now().isoformat(timespec="seconds")
    summary_text = load_template("summary.txt").format(
        work_request_no=ctx.work_request_no,
        registry_key=ctx.registry_key,
        command=ctx.command,
        mode=ctx.mode,
        finalized_at=finalized_at,
    )
    ctx.summary_txt_path().write_text(summary_text, encoding="utf-8")
    ctx.usage_json_path().write_text("{}\n", encoding="utf-8")
    write_metadata(ctx, finalized_at=finalized_at)
    step_end(ctx, "DONE", outcome="ok")
    # 12Rule re-verification (after completing REPORT + recording step.end DONE — workflow_step already DONE)
    verdict_report = evaluate_12_rules(ctx)
    save_verdict_report(ctx, verdict_report)
    final_verdict = build_final_verdict(ctx, verdict_report)
    save_final_verdict(ctx, final_verdict)
    emit(
        ctx,
        "validate.verdict",
        verdict=verdict_report.verdict,
        violation_count=verdict_report.violation_count(),
        has_hard_fail=verdict_report.has_hard_fail(),
        work_request=ctx.work_request_no,
        final_verdict_path=str(ctx.final_verdict_json_path()),
    )
    if final_verdict["blocking_failures"]:
        regression(
            ctx,
            "complete_blocked",
            blocking_failures=final_verdict["blocking_failures"],
            final_verdict_path=str(ctx.final_verdict_json_path()),
        )
        workflow_finish(
            ctx,
            outcome="fail",
            verdict=verdict_report.verdict,
            summary="Complete blocked by verification gates",
            final_verdict_path=str(ctx.final_verdict_json_path()),
            work_request_refinement=final_verdict.get("work_request_refinement", {}),
        )
        return
    workflow_finish(
        ctx,
        outcome="ok",
        verdict=verdict_report.verdict,
        final_verdict_path=str(ctx.final_verdict_json_path()),
        work_request_refinement=final_verdict.get("work_request_refinement", {}),
    )
    conveyor_move(ctx.work_request_no, "verifying")


def fail_step(ctx: WorkflowContext, reason: str) -> None:
    """FAILED — failure.md + conveyor autoregressive"""
    failure_body = load_template("failure.md").format(
        work_request_no=ctx.work_request_no,
        registry_key=ctx.registry_key,
        reason=reason,
        ts=datetime.now().isoformat(timespec="seconds"),
    )
    ctx.failure_md_path().write_text(failure_body, encoding="utf-8")
    write_metadata(ctx, failure_reason=reason)
    regression(ctx, "workflow_step_failed", reason=reason)
    workflow_finish(ctx, outcome="fail", verdict="FAIL")
    update_step(ctx, ctx.current_step, "FAILED", note=reason)
