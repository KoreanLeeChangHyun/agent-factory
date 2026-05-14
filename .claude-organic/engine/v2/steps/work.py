"""WORK Step — Phase loop. spawn_mode 에 따라 in_place / subprocess."""

from __future__ import annotations

from .._common import WorkflowContext, load_prompt, write_context
from .._emitter import phase_end, phase_start
from .._retry import spawn_with_retry
from .._spawn import logical_session_name, new_session_uuid
from .._verify import (
    Phase,
    parse_plan_frontmatter,
    topo_sort,
    verify_work_md,
    verify_work_set,
)
from .done import fail_step


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


def _load_deps_block(ctx: WorkflowContext, phase: Phase) -> str:
    blocks: list[str] = []
    for dep_id in phase.deps:
        dep_path = ctx.work_dir_phase_md(dep_id)
        if dep_path.exists():
            blocks.append(
                f"### work/{dep_id}.md\n\n{dep_path.read_text(encoding='utf-8')}\n"
            )
    return "\n".join(blocks) if blocks else "(종속 없음)"


def work_step(ctx: WorkflowContext) -> bool:
    """Returns: True 정상 / False phases empty 또는 topo 실패 (fail_step 처리됨)."""
    phases = _load_plan(ctx)
    if not phases:
        fail_step(ctx, "plan.md phases empty or topo sort failed")
        return False
    has_subprocess_mode = any(p.spawn_mode == "subprocess" for p in phases)
    plan_body = ctx.plan_md_path().read_text(encoding="utf-8")
    work_system_prompt = load_prompt("work")

    if has_subprocess_mode:
        for phase in phases:
            phase_start(ctx, phase.id, spawn_mode=phase.spawn_mode)
            dep_blocks = _load_deps_block(ctx, phase)
            initial_prompt = (
                f"plan.md (통째):\n{plan_body}\n\n"
                f"종속 Phase 산출물:\n{dep_blocks}\n\n"
                f"본 Phase: {phase.id} — {phase.title}\n"
                f"산출물: `{ctx.work_dir_phase_md(phase.id)}` 에 작성."
            )
            session_id = new_session_uuid()
            logical = logical_session_name(ctx.ticket_no, "WORK", phase.id)
            ctx.session_ids[logical] = session_id
            write_context(ctx)
            v, _, _ = spawn_with_retry(
                ctx,
                step="WORK",
                initial_prompt=initial_prompt,
                system_prompt=work_system_prompt,
                session_id=session_id,
                verify=lambda p=phase: verify_work_md(ctx.work_dir_phase_md(p.id)),
                artifact_path=ctx.work_dir_phase_md(phase.id),
            )
            phase_end(ctx, phase.id, outcome="ok" if v.ok else "fail")
    else:
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
        session_id = new_session_uuid()
        logical = logical_session_name(ctx.ticket_no, "WORK")
        ctx.session_ids[logical] = session_id
        write_context(ctx)
        artifact_paths = [ctx.work_dir_phase_md(p.id) for p in phases]
        spawn_with_retry(
            ctx,
            step="WORK",
            initial_prompt=initial_prompt,
            system_prompt=work_system_prompt,
            session_id=session_id,
            verify=lambda: verify_work_set(artifact_paths),
            artifact_path=ctx.work_dir / "work",
        )
    return True
