"""v2 driver — entrypoint + 6 Step orchestration.

SPEC.md §7 (책임 분담) + §7.2 의사 코드. LLM 호출 0 (claude -p subprocess 만).

본 모듈은 1차 골격. steps/ 디렉터리 분리 + prompts/*.txt 외부화 + tests/
는 Phase 2-B 후속.

CLI:
    python -m engine.v2.driver T-NNN
    python -m engine.v2.driver T-NNN --step PLAN
    python -m engine.v2.driver T-NNN --abort
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from ._common import (
    PROJECT_ROOT,
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
from ._emitter import (
    emit,
    phase_end,
    phase_start,
    regression,
    step_end,
    step_start,
    workflow_finish,
)
from ._retry import spawn_with_retry
from ._spawn import session_id_for
from ._verify import (
    Phase,
    parse_plan_frontmatter,
    topo_sort,
    verify_plan_md,
    verify_report_md,
    verify_validate_md,
    verify_work_md,
    verify_work_set,
)


# -------- Step prompts (1차 inline. Phase 2-B 에서 prompts/*.txt 분리) --------

PLAN_SYSTEM_PROMPT = """당신은 워크플로우 v2 의 PLAN Step 입니다.
산출물: plan.md (YAML frontmatter + body).
frontmatter 필수 키: schema_version, ticket, command, mode, phases.
phases[] 의 각 항목: id, title, deps (list), deliverable, spawn_mode (in_place/subprocess).
LLM 호출은 본 1회만. 다른 도구 사용 최소화. 산출물 파일 직접 write.
"""

WORK_SYSTEM_PROMPT = """당신은 워크플로우 v2 의 WORK Step 입니다.
plan.md 의 phases 를 순차 처리. 각 Phase 마다 work/<id>.md 산출물 작성.
종속 (deps) 이 있으면 이미 작성된 work/<dep>.md 참조 가능.
산출물 파일에 직접 write (Bash/Edit/Write 도구 활용).
"""

VALIDATE_SYSTEM_PROMPT = """당신은 워크플로우 v2 의 VALIDATE Step 입니다.
plan.md + work/*.md 검증. validate-report.md 작성.
12 룰 (R-EXIST/R-METRIC/R-GUARD/R-PATH/R-FSM/R-WT) 평가. verdict: PASS/WARN/FAIL/SKIP.
advisory only — 자동 차단 0건.
"""

REPORT_SYSTEM_PROMPT = """당신은 워크플로우 v2 의 REPORT Step 입니다.
plan.md + 모든 work/*.md + validate-report.md 통째 종합.
report.md 작성. 본문에 'plan.md' 토큰 포함 필수 (R-PATH-1).
"""


# -------- Step 함수 --------


def init_step(ticket_no: str) -> WorkflowContext:
    """INIT — driver in-process. kanban Open→In Progress, work_dir + 초기 status.json."""
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
    # 티켓 prompt → user_prompt.txt
    ticket_dump = kanban_show(ticket_no)
    ctx.user_prompt_path().write_text(ticket_dump, encoding="utf-8")
    # 초기 status.json + .context.json
    write_status(ctx, {"workflow_step": "INIT", "transitions": []})
    write_context(ctx)
    append_log(ctx, f"INIT — registry_key={registry_key}, ticket={ticket_no}")
    step_start(ctx, "INIT")
    kanban_move(ticket_no, "progress")
    step_end(ctx, "INIT", outcome="ok")
    update_step(ctx, "INIT", "PLAN")
    return ctx


def plan_step(ctx: WorkflowContext) -> None:
    """PLAN — claude -p 1 spawn → plan.md."""
    ticket_dump = ctx.user_prompt_path().read_text(encoding="utf-8")
    initial_prompt = (
        f"티켓 prompt:\n{ticket_dump}\n\n"
        f"위 티켓의 작업을 phase 단위로 분해해 plan.md (frontmatter + body) 를 "
        f"`{ctx.plan_md_path()}` 에 작성하세요."
    )
    session_id = session_id_for(ctx.ticket_no, "PLAN")
    ctx.session_ids["PLAN"] = session_id
    write_context(ctx)
    spawn_with_retry(
        ctx,
        step="PLAN",
        initial_prompt=initial_prompt,
        system_prompt=PLAN_SYSTEM_PROMPT,
        session_id=session_id,
        verify=lambda: verify_plan_md(ctx.plan_md_path()),
        artifact_path=ctx.plan_md_path(),
    )


def _load_plan(ctx: WorkflowContext) -> list[Phase]:
    text = ctx.plan_md_path().read_text(encoding="utf-8")
    fm = parse_plan_frontmatter(text)
    if fm is None or not fm.phases:
        return []
    ordered = topo_sort(fm.phases)
    if ordered is None:
        return []
    ctx.mode = fm.mode
    ctx.command = fm.command
    return ordered


def work_step(ctx: WorkflowContext) -> None:
    """WORK — Phase loop. plan.md 의 spawn_mode 에 따라 in_place / subprocess."""
    phases = _load_plan(ctx)
    if not phases:
        # plan.md 회귀 — driver 가 PLAN 재시도로 못 살린 case (이미 step_end fail emit 됨)
        return
    has_subprocess_mode = any(p.spawn_mode == "subprocess" for p in phases)
    plan_body = ctx.plan_md_path().read_text(encoding="utf-8")

    if has_subprocess_mode:
        # 격리 모드 — Phase 마다 별도 subprocess
        for phase in phases:
            phase_start(ctx, phase.id, spawn_mode=phase.spawn_mode)
            dep_blocks = _load_deps_block(ctx, phase)
            initial_prompt = (
                f"plan.md (통째):\n{plan_body}\n\n"
                f"종속 Phase 산출물:\n{dep_blocks}\n\n"
                f"본 Phase: {phase.id} — {phase.title}\n"
                f"산출물: `{ctx.work_dir_phase_md(phase.id)}` 에 작성."
            )
            session_id = session_id_for(ctx.ticket_no, "WORK", phase.id)
            ctx.session_ids[f"WORK-{phase.id}"] = session_id
            write_context(ctx)
            v, _, _ = spawn_with_retry(
                ctx,
                step="WORK",
                initial_prompt=initial_prompt,
                system_prompt=WORK_SYSTEM_PROMPT,
                session_id=session_id,
                verify=lambda p=phase: verify_work_md(ctx.work_dir_phase_md(p.id)),
                artifact_path=ctx.work_dir_phase_md(phase.id),
            )
            phase_end(ctx, phase.id, outcome="ok" if v.ok else "fail")
    else:
        # default — 1 subprocess 안에서 순차 처리 (SPEC.md §5.3 in_place)
        phase_list_text = "\n".join(
            f"- {p.id}: {p.title} (deps={p.deps}, deliverable={p.deliverable})"
            for p in phases
        )
        initial_prompt = (
            f"plan.md (통째):\n{plan_body}\n\n"
            f"본 1 subprocess 안에서 다음 Phase 들을 topological 순서대로 처리:\n"
            f"{phase_list_text}\n\n"
            f"각 Phase 산출물을 `work/<id>.md` 에 작성. 모두 작성한 뒤 종료."
        )
        session_id = session_id_for(ctx.ticket_no, "WORK")
        ctx.session_ids["WORK"] = session_id
        write_context(ctx)
        artifact_paths = [ctx.work_dir_phase_md(p.id) for p in phases]
        spawn_with_retry(
            ctx,
            step="WORK",
            initial_prompt=initial_prompt,
            system_prompt=WORK_SYSTEM_PROMPT,
            session_id=session_id,
            verify=lambda: verify_work_set(artifact_paths),
            artifact_path=ctx.work_dir / "work",
        )


def _load_deps_block(ctx: WorkflowContext, phase: Phase) -> str:
    blocks: list[str] = []
    for dep_id in phase.deps:
        dep_path = ctx.work_dir_phase_md(dep_id)
        if dep_path.exists():
            blocks.append(f"### work/{dep_id}.md\n\n{dep_path.read_text(encoding='utf-8')}\n")
    return "\n".join(blocks) if blocks else "(종속 없음)"


def validate_step(ctx: WorkflowContext) -> None:
    """VALIDATE — claude -p 1 spawn → validate-report.md."""
    plan_body = ctx.plan_md_path().read_text(encoding="utf-8")
    work_blocks: list[str] = []
    work_dir = ctx.work_dir / "work"
    if work_dir.exists():
        for md in sorted(work_dir.glob("*.md")):
            work_blocks.append(f"### work/{md.name}\n\n{md.read_text(encoding='utf-8')}\n")
    initial_prompt = (
        f"plan.md (통째):\n{plan_body}\n\n"
        f"work/*.md (모두 통째):\n{'\\n'.join(work_blocks)}\n\n"
        f"12 룰 advisory 평가 + 추가 quality 검증을 `{ctx.validate_report_md_path()}` 에 작성."
    )
    session_id = session_id_for(ctx.ticket_no, "VALIDATE")
    ctx.session_ids["VALIDATE"] = session_id
    write_context(ctx)
    spawn_with_retry(
        ctx,
        step="VALIDATE",
        initial_prompt=initial_prompt,
        system_prompt=VALIDATE_SYSTEM_PROMPT,
        session_id=session_id,
        verify=lambda: verify_validate_md(ctx.validate_report_md_path()),
        artifact_path=ctx.validate_report_md_path(),
    )


def report_step(ctx: WorkflowContext) -> None:
    """REPORT — claude -p 1 spawn → report.md (plan + work + validate 통째 inject)."""
    plan_body = ctx.plan_md_path().read_text(encoding="utf-8")
    work_blocks: list[str] = []
    work_dir = ctx.work_dir / "work"
    if work_dir.exists():
        for md in sorted(work_dir.glob("*.md")):
            work_blocks.append(f"### work/{md.name}\n\n{md.read_text(encoding='utf-8')}\n")
    validate_body = (
        ctx.validate_report_md_path().read_text(encoding="utf-8")
        if ctx.validate_report_md_path().exists()
        else ""
    )
    initial_prompt = (
        f"plan.md:\n{plan_body}\n\n"
        f"work/*.md:\n{'\\n'.join(work_blocks)}\n\n"
        f"validate-report.md:\n{validate_body}\n\n"
        f"위를 통째 종합한 report.md 를 `{ctx.report_md_path()}` 에 작성. "
        f"본문에 'plan.md' 토큰 포함 필수."
    )
    session_id = session_id_for(ctx.ticket_no, "REPORT")
    ctx.session_ids["REPORT"] = session_id
    write_context(ctx)
    spawn_with_retry(
        ctx,
        step="REPORT",
        initial_prompt=initial_prompt,
        system_prompt=REPORT_SYSTEM_PROMPT,
        session_id=session_id,
        verify=lambda: verify_report_md(ctx.report_md_path(), ctx.plan_md_path()),
        artifact_path=ctx.report_md_path(),
    )


def done_step(ctx: WorkflowContext) -> None:
    """DONE — driver in-process. summary.txt + usage.json + kanban move review."""
    step_start(ctx, "DONE")
    summary_text = (
        f"Workflow v2 finalize\n"
        f"ticket={ctx.ticket_no}\n"
        f"registry_key={ctx.registry_key}\n"
        f"command={ctx.command}\n"
        f"mode={ctx.mode}\n"
        f"finalized_at={datetime.now().isoformat(timespec='seconds')}\n"
    )
    ctx.summary_txt_path().write_text(summary_text, encoding="utf-8")
    # usage.json 은 claude -p subprocess 산출물이 별도 — 1차 prototype 은 빈 객체
    ctx.usage_json_path().write_text("{}\n", encoding="utf-8")
    step_end(ctx, "DONE", outcome="ok")
    workflow_finish(ctx, outcome="ok")
    update_step(ctx, ctx.current_step, "DONE")
    kanban_move(ctx.ticket_no, "review")


def fail_step(ctx: WorkflowContext, reason: str) -> None:
    """FAILED — failure.md 작성 + kanban 자동 회귀 X (SPEC.md §12.4)."""
    ctx.failure_md_path().write_text(
        f"# Workflow FAILED\n\n"
        f"- ticket: {ctx.ticket_no}\n"
        f"- registry_key: {ctx.registry_key}\n"
        f"- reason: {reason}\n"
        f"- ts: {datetime.now().isoformat(timespec='seconds')}\n",
        encoding="utf-8",
    )
    regression(ctx, "workflow_step_failed", reason=reason)
    workflow_finish(ctx, outcome="fail", verdict="FAIL")
    update_step(ctx, ctx.current_step, "FAILED", note=reason)


# -------- main --------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="v2 workflow driver")
    parser.add_argument("ticket", help="T-NNN")
    parser.add_argument(
        "--step",
        choices=["INIT", "PLAN", "WORK", "VALIDATE", "REPORT", "DONE"],
        help="(디버그) 특정 Step 만 실행. registry_key 는 신규 발급.",
    )
    args = parser.parse_args(argv)

    ctx = init_step(args.ticket)
    if args.step == "INIT":
        return 0

    try:
        # PLAN
        plan_step(ctx)
        if not ctx.plan_md_path().exists():
            fail_step(ctx, "plan.md not produced after retries")
            return 2
        update_step(ctx, "PLAN", "WORK")
        if args.step == "PLAN":
            return 0

        # WORK
        work_step(ctx)
        update_step(ctx, "WORK", "VALIDATE")
        if args.step == "WORK":
            return 0

        # VALIDATE
        validate_step(ctx)
        update_step(ctx, "VALIDATE", "REPORT")
        if args.step == "VALIDATE":
            return 0

        # REPORT
        report_step(ctx)
        if not ctx.report_md_path().exists():
            fail_step(ctx, "report.md not produced after retries")
            return 2
        update_step(ctx, "REPORT", "DONE")
        if args.step == "REPORT":
            return 0

        # DONE
        done_step(ctx)
        return 0
    except Exception as exc:
        fail_step(ctx, f"unhandled exception: {exc!r}")
        return 3


if __name__ == "__main__":
    sys.exit(main())
