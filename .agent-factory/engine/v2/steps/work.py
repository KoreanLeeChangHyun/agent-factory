"""WORK Step — Phase loop. spawn_mode 에 따라 in_place / subprocess.

T-504 cutover — `plan/plan.json` (SSOT) 를 parse_plan_json 으로 로딩.
plan body inject 는 `plan/plan.md` (자연어 본문) 사용.

T-506 — subprocess 모드 분기는 topo_levels + parallel_spawn 으로 같은 level 동시
spawn + phase.workers > 1 시 nested parallel_spawn 으로 N worker 동시 spawn.
in_place 경로는 기존 단일 subprocess 보존 (회귀 0).
"""

from __future__ import annotations

import threading

from .._common import (
    WorkflowContext,
    append_log,
    auto_commit,
    get_fail_policy,
    get_max_parallel,
    load_prompt,
    write_context,
)
from .._emitter import phase_end, phase_start
from .._parallel import parallel_spawn
from .._retry import spawn_with_retry
from .._spawn import logical_session_name, new_session_uuid
from .._verify import (
    Phase,
    VerifyResult,
    verify_work_md,
    verify_work_md_multi,
    verify_work_set,
)
from ..core.plan_loader import PlanLoaderError, parse_plan_json, topo_levels, topo_sort
from .done import fail_step


# session_ids dict assignment 은 GIL 보호이지만 명시 lock 으로 readability ↑
_SESSION_IDS_LOCK = threading.Lock()


def _load_plan(ctx: WorkflowContext) -> list[Phase]:
    """`plan/plan.json` 을 읽어 topo 정렬된 Phase 리스트 반환. 실패 시 []."""
    try:
        plan = parse_plan_json(ctx.plan_json_path())
    except PlanLoaderError:
        return []
    ordered = topo_sort(plan.phases)
    if ordered is None:
        return []
    ctx.mode = plan.mode
    ctx.command = plan.command
    return ordered


def _load_deps_block(ctx: WorkflowContext, phase: Phase) -> str:
    blocks: list[str] = []
    for dep_id in phase.deps:
        dep_path = ctx.work_phase_md_resolved(dep_id)
        if dep_path.exists():
            rel = dep_path.relative_to(ctx.work_dir)
            blocks.append(
                f"### {rel.as_posix()}\n\n{dep_path.read_text(encoding='utf-8')}\n"
            )
    return "\n".join(blocks) if blocks else "(종속 없음)"


def _read_plan_body(ctx: WorkflowContext) -> str:
    """`plan/plan.md` (자연어 본문) 읽기. 미존재 시 빈 문자열 — driver retry 가 처리."""
    md_path = ctx.plan_md_path()
    if not md_path.exists():
        return ""
    return md_path.read_text(encoding="utf-8")


def _record_session_id(ctx: WorkflowContext, logical: str, session_id: str) -> None:
    """ctx.session_ids 에 thread-safe 박제 + context.json append."""
    with _SESSION_IDS_LOCK:
        ctx.session_ids[logical] = session_id
        write_context(ctx)


def _spawn_one_worker(
    ctx: WorkflowContext,
    phase: Phase,
    worker_idx: int,
    *,
    plan_body: str,
    work_system_prompt: str,
) -> tuple[VerifyResult, str]:
    """phase 안 1 worker spawn → W<n>.md 작성 검증.

    Returns: (VerifyResult, session_id) — session_id 는 phase_start/end emit 박제용.
    workers=1 (default) 일 때도 동일 경로. worker_idx 1-based.
    """
    artifact_path = ctx.work_phase_w_md(phase.id, worker_idx)
    dep_blocks = _load_deps_block(ctx, phase)
    worker_label = (
        f"(worker {worker_idx}/{phase.workers})" if phase.workers > 1 else ""
    )
    initial_prompt = (
        f"plan.md (통째):\n{plan_body}\n\n"
        f"종속 Phase 산출물:\n{dep_blocks}\n\n"
        f"본 Phase: {phase.id} — {phase.title} {worker_label}\n"
        f"산출물: `{artifact_path}` 에 작성."
    )
    session_id = new_session_uuid()
    logical = logical_session_name(ctx.ticket_no, "WORK", f"{phase.id}-W{worker_idx}")
    _record_session_id(ctx, logical, session_id)
    v, _, _ = spawn_with_retry(
        ctx,
        step="WORK",
        initial_prompt=initial_prompt,
        system_prompt=work_system_prompt,
        session_id=session_id,
        verify=lambda p=artifact_path: verify_work_md(p),
        artifact_path=artifact_path,
    )
    return v, session_id


def _spawn_one_phase(
    ctx: WorkflowContext,
    phase: Phase,
    *,
    plan_body: str,
    work_system_prompt: str,
) -> VerifyResult:
    """1 phase 처리 — workers=1 (default) 또는 workers>1 nested parallel_spawn.

    SPEC §0.1 — driver 결정론 영역. phase_start/end emit 박제.
    T-506 P7 — phase 단위 emit 1쌍. workers>1 시 session_ids list 를 extra payload 박제.
    """
    workers = max(1, int(phase.workers or 1))
    if workers == 1:
        result, session_id = _spawn_one_worker(
            ctx,
            phase,
            1,
            plan_body=plan_body,
            work_system_prompt=work_system_prompt,
        )
        # T-506 P7 — workers=1 케이스는 단일 session_id 박제
        phase_start(
            ctx,
            phase.id,
            session_id=session_id,
            worker_index=1,
            spawn_mode=phase.spawn_mode,
            workers=workers,
        )
        phase_end(
            ctx,
            phase.id,
            outcome="ok" if result.ok else "fail",
            session_id=session_id,
            worker_index=1,
        )
        return result

    # workers > 1 — N worker 동시 spawn
    phase_start(
        ctx,
        phase.id,
        spawn_mode=phase.spawn_mode,
        workers=workers,
    )
    worker_indices = list(range(1, workers + 1))
    outcomes = parallel_spawn(
        worker_indices,
        fn=lambda i: _spawn_one_worker(
            ctx,
            phase,
            i,
            plan_body=plan_body,
            work_system_prompt=work_system_prompt,
        ),
        max_workers=workers,
        fail_fast=get_fail_policy() == "fail_fast",
    )
    artifact_paths = [ctx.work_phase_w_md(phase.id, i) for i in worker_indices]
    result = verify_work_md_multi(artifact_paths)
    session_ids: list[str] = []
    for o in outcomes:
        if o.ok and isinstance(o.value, tuple) and len(o.value) == 2:
            session_ids.append(o.value[1])
        else:
            session_ids.append("")
        if not o.ok and o.exception is not None:
            result.missing.append(
                f"worker {o.item} exception: {type(o.exception).__name__}"
            )
    phase_end(
        ctx,
        phase.id,
        outcome="ok" if result.ok else "fail",
        session_ids=session_ids,
    )
    return result


def _phase_outcome_ok(outcome) -> bool:
    """parallel_spawn 결과를 phase 성공 여부로 환산.

    `_spawn_one_phase` 가 VerifyResult 를 반환하므로 `outcome.ok` (예외 무여부) 만으로는
    부족. 실제 산출물 검증 결과 (`VerifyResult.ok`) 까지 확인.
    """
    if not outcome.ok:
        return False
    value = outcome.value
    if isinstance(value, VerifyResult):
        return value.ok
    # _spawn_one_worker tuple (VerifyResult, session_id) — inner parallel_spawn 호환
    if isinstance(value, tuple) and len(value) == 2 and isinstance(value[0], VerifyResult):
        return value[0].ok
    return True


def _run_subprocess_mode(
    ctx: WorkflowContext,
    phases: list[Phase],
    *,
    plan_body: str,
    work_system_prompt: str,
) -> None:
    """T-506 P5 — phase 간 level 병렬 spawn (subprocess 모드).

    `topo_levels` 로 level 별 묶음 → 같은 level 동시 spawn → 모두 완료 후
    다음 level 진입. fail_fast 정책은 level 안 phase 들에만 적용 — 다음 level
    진입 여부는 본 함수가 결정 (level 단위 fail 검출 시 break).
    """
    levels = topo_levels(phases)
    fail_fast = get_fail_policy() == "fail_fast"
    max_par = get_max_parallel()
    append_log(
        ctx,
        f"[WORK] subprocess 모드 {len(levels)} level, "
        f"max_parallel={max_par}, fail_policy={'fail_fast' if fail_fast else 'fail_tolerant'}",
    )
    for level_idx, level_phases in enumerate(levels):
        append_log(
            ctx,
            f"[WORK] level {level_idx}: {len(level_phases)} phase 동시 spawn "
            f"({[p.id for p in level_phases]})",
        )
        outcomes = parallel_spawn(
            level_phases,
            fn=lambda phase: _spawn_one_phase(
                ctx,
                phase,
                plan_body=plan_body,
                work_system_prompt=work_system_prompt,
            ),
            max_workers=max_par,
            fail_fast=fail_fast,
        )
        any_fail = any(not _phase_outcome_ok(o) for o in outcomes)
        for o in outcomes:
            phase = o.item
            status = "OK" if _phase_outcome_ok(o) else "FAIL"
            append_log(ctx, f"[WORK] level {level_idx} phase {phase.id} {status}")
        if any_fail and fail_fast:
            append_log(
                ctx,
                f"[WORK] level {level_idx} 실패 감지 (fail_fast) — 다음 level 차단",
            )
            break


def _run_in_place_mode(
    ctx: WorkflowContext,
    phases: list[Phase],
    *,
    plan_body: str,
    work_system_prompt: str,
) -> None:
    """기존 in_place 모드 — 1 subprocess 안에서 phase 순차. 회귀 0."""
    phase_list_text = "\n".join(
        f"- {p.id}: {p.title} (deps={p.deps}, deliverable={p.deliverable})"
        for p in phases
    )
    initial_prompt = (
        f"plan.md (통째):\n{plan_body}\n\n"
        f"본 1 subprocess 안에서 다음 Phase 들을 topological 순서대로 처리:\n"
        f"{phase_list_text}\n\n"
        f"각 Phase 산출물을 plan.json frontmatter 의 deliverable 경로에 작성 "
        f"(권장: `work/<id>/W1.md` nested / 허용: `work/<id>.md` flat). "
        f"모두 작성한 뒤 종료."
    )
    session_id = new_session_uuid()
    logical = logical_session_name(ctx.ticket_no, "WORK")
    ctx.session_ids[logical] = session_id
    write_context(ctx)
    artifact_paths = [ctx.work_phase_md_resolved(p.id) for p in phases]
    spawn_with_retry(
        ctx,
        step="WORK",
        initial_prompt=initial_prompt,
        system_prompt=work_system_prompt,
        session_id=session_id,
        verify=lambda: verify_work_set(artifact_paths),
        artifact_path=ctx.work_dir / "work",
    )
    for p in phases:
        artifact = ctx.work_phase_md_resolved(p.id)
        ok = artifact.is_file() and artifact.stat().st_size > 0
        append_log(
            ctx,
            f"[WORK] Phase {p.id} 산출물 {'OK' if ok else 'MISS'} "
            f"({artifact.relative_to(ctx.work_dir)})",
        )


def work_step(ctx: WorkflowContext) -> bool:
    """Returns: True 정상 / False phases empty 또는 topo 실패 (fail_step 처리됨)."""
    phases = _load_plan(ctx)
    if not phases:
        fail_step(ctx, "plan.json phases empty or topo sort failed")
        return False
    has_subprocess_mode = any(p.spawn_mode == "subprocess" for p in phases)
    plan_body = _read_plan_body(ctx)
    work_system_prompt = load_prompt("work")

    mode_label = "subprocess (격리)" if has_subprocess_mode else "in_place (단일 spawn)"
    append_log(ctx, f"[WORK] {len(phases)} Phase 진행 시작 (spawn_mode={mode_label})")
    for p in phases:
        append_log(
            ctx,
            f"[WORK] Phase {p.id}: {p.title} "
            f"(deps={p.deps}, spawn_mode={p.spawn_mode}, workers={p.workers})",
        )

    if has_subprocess_mode:
        _run_subprocess_mode(
            ctx,
            phases,
            plan_body=plan_body,
            work_system_prompt=work_system_prompt,
        )
    else:
        _run_in_place_mode(
            ctx,
            phases,
            plan_body=plan_body,
            work_system_prompt=work_system_prompt,
        )
    # SPEC §0.1 (Stage 3-E) — worker 산출물 결정론 commit (변경 0건 skip).
    auto_commit(ctx)
    return True
