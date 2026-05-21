"""REPORT Step — claude -p 1 spawn → report.html (T-504 cutover).

Output Format Canon §1 Area 3 — Human readable HTML. plan/plan.md (LLM Natural Language) +
work/**/*.md (Phase calculation) + validate/report.md (Quality evaluation) whole inject.
LLM creates `report.html` by filling in the `templates/report.html` placeholder.
"""

from __future__ import annotations

import json

from engine.application.reporting.prompt import (
    ReportPromptInput,
    build_report_initial_prompt,
)
from engine.core.reporting.templates import report_template_path

from .._common import (
    WorkflowContext,
    load_prompt,
    write_context,
)
from .._retry import spawn_with_retry
from .._spawn import logical_session_name, new_session_uuid
from .._verdict import read_verify_verdict, write_report_manifest
from .._verify import verify_report_html


def report_step(ctx: WorkflowContext) -> None:
    plan_md_path = ctx.plan_md_path()
    plan_body = (
        plan_md_path.read_text(encoding="utf-8") if plan_md_path.exists() else ""
    )
    work_blocks: list[str] = []
    work_dir = ctx.work_dir / "work"
    if work_dir.exists():
        for md in sorted(work_dir.glob("**/*.md")):
            rel = md.relative_to(work_dir)
            work_blocks.append(
                f"### work/{rel.as_posix()}\n\n{md.read_text(encoding='utf-8')}\n"
            )
    joined_work = "\n".join(work_blocks) if work_blocks else "(work/empty)"
    validate_body = (
        ctx.validate_report_md_path().read_text(encoding="utf-8")
        if ctx.validate_report_md_path().exists()
        else ""
    )
    verify_verdict = read_verify_verdict(ctx)
    verify_verdict_body = (
        json.dumps(verify_verdict, ensure_ascii=False, indent=2)
        if verify_verdict
        else "{}"
    )
    initial_prompt = build_report_initial_prompt(
        ReportPromptInput(
            plan_body=plan_body,
            joined_work=joined_work,
            validate_body=validate_body,
            verify_verdict_body=verify_verdict_body,
            report_html_path=ctx.report_html_path(),
            template_path=report_template_path(),
        )
    )
    session_id = new_session_uuid()
    logical = logical_session_name(ctx.work_request_no, "REPORT")
    ctx.session_ids[logical] = session_id
    write_context(ctx)
    spawn_with_retry(
        ctx,
        step="REPORT",
        initial_prompt=initial_prompt,
        system_prompt=load_prompt("report"),
        session_id=session_id,
        verify=lambda: verify_report_html(
            ctx.report_html_path(), ctx.plan_md_path()
        ),
        artifact_path=ctx.report_html_path(),
    )
    write_report_manifest(ctx)
