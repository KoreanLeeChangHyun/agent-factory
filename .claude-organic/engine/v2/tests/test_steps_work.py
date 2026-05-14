"""test_steps_work.py — steps/work.py 단위 테스트.

대상:
  - _load_plan (plan.md 정합 / 미존재 / circular dep → [])
  - _load_deps_block (deps 산출물 inject / 없을 때 fallback)
  - work_step empty phases → fail_step + return False (Phase 2-A #6 회귀 영역)
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import patch

from engine.v2._common import WorkflowContext, write_status
from engine.v2._verify import Phase
from engine.v2.steps.work import _load_deps_block, _load_plan, work_step


def _make_ctx(tmp_path: Path) -> WorkflowContext:
    (tmp_path / "work").mkdir(exist_ok=True)
    ctx = WorkflowContext(
        ticket_no="T-489",
        registry_key="20260515-000000",
        work_dir=tmp_path,
        current_step="WORK",
    )
    write_status(ctx, {"workflow_step": "WORK", "transitions": []})
    return ctx


def _write_plan(ctx: WorkflowContext, body: str) -> None:
    ctx.plan_md_path().write_text(body, encoding="utf-8")


def test_load_plan_normal(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    _write_plan(ctx, textwrap.dedent(
        """\
        ---
        schema_version: 1
        ticket: T-489
        command: implement
        mode: multi
        phases:
          - id: P1
            title: "x"
            deps: []
            deliverable: work/P1.md
          - id: P2
            title: "y"
            deps: [P1]
            deliverable: work/P2.md
        ---

        body
        """
    ))
    phases = _load_plan(ctx)
    assert len(phases) == 2
    # topo 순서 — P1 먼저
    assert phases[0].id == "P1"
    assert phases[1].id == "P2"
    assert ctx.mode == "multi"
    assert ctx.command == "implement"


def test_load_plan_circular_returns_empty(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    _write_plan(ctx, textwrap.dedent(
        """\
        ---
        schema_version: 1
        ticket: T-1
        phases:
          - id: A
            title: ""
            deps: [B]
          - id: B
            title: ""
            deps: [A]
        ---

        body
        """
    ))
    assert _load_plan(ctx) == []


def test_load_plan_empty_phases(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    _write_plan(ctx, textwrap.dedent(
        """\
        ---
        schema_version: 1
        ticket: T-1
        phases: []
        ---

        body
        """
    ))
    assert _load_plan(ctx) == []


def test_load_deps_block_with_deps(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    ctx.work_dir_phase_md("P1").write_text("P1 산출물 본문", encoding="utf-8")
    phase = Phase(id="P2", title="next", deps=["P1"])
    block = _load_deps_block(ctx, phase)
    assert "P1 산출물 본문" in block
    assert "work/P1.md" in block


def test_load_deps_block_no_deps(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    phase = Phase(id="P1", title="first", deps=[])
    assert _load_deps_block(ctx, phase) == "(종속 없음)"


def test_work_step_empty_phases_fails(tmp_path: Path) -> None:
    """Phase 2-A #6 회귀 영역 — phases empty 시 fail_step + return False."""
    ctx = _make_ctx(tmp_path)
    _write_plan(ctx, textwrap.dedent(
        """\
        ---
        schema_version: 1
        ticket: T-1
        phases: []
        ---

        body
        """
    ))
    result = work_step(ctx)
    assert result is False
    # fail_step 이 호출되어 failure.md 작성됨
    assert ctx.failure_md_path().exists()
    failure_text = ctx.failure_md_path().read_text(encoding="utf-8")
    assert "plan.md phases empty" in failure_text


def test_work_step_topo_fail_invokes_fail_step(tmp_path: Path) -> None:
    """circular dep 도 동일 흐름 — _load_plan 이 [] 반환 → fail_step."""
    ctx = _make_ctx(tmp_path)
    _write_plan(ctx, textwrap.dedent(
        """\
        ---
        schema_version: 1
        ticket: T-1
        phases:
          - id: A
            deps: [B]
          - id: B
            deps: [A]
        ---

        body
        """
    ))
    assert work_step(ctx) is False
    assert ctx.failure_md_path().exists()
