"""test_steps_work.py — steps/work.py 단위 테스트 (T-504 cutover).

T-504 cutover — `plan/plan.json` 을 fixture 로 작성, `_load_plan` 이 parse_plan_json
경유. 옛 YAML frontmatter inline fixture 통째 폐기.

대상:
  - _load_plan (plan.json 정합 / 미존재 / circular dep → [])
  - _load_deps_block (deps 산출물 inject / 없을 때 fallback)
  - work_step empty phases → fail_step + return False
"""

from __future__ import annotations

import json
from pathlib import Path

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


def _write_plan_json(ctx: WorkflowContext, payload: dict) -> None:
    ctx.plan_dir().mkdir(parents=True, exist_ok=True)
    ctx.plan_json_path().write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    ctx.plan_md_path().write_text(
        "# plan body\n자연어 본문 (20자 이상 확보)\n" + "x" * 30,
        encoding="utf-8",
    )


def test_load_plan_normal(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    _write_plan_json(
        ctx,
        {
            "schema_version": 2,
            "ticket": "T-489",
            "command": "implement",
            "mode": "multi",
            "phases": [
                {
                    "id": "P1",
                    "title": "x",
                    "deps": [],
                    "deliverable": "work/P1/W1.md",
                    "spawn_mode": "in_place",
                    "workers": 1,
                    "acceptance_criteria": ["a"],
                },
                {
                    "id": "P2",
                    "title": "y",
                    "deps": ["P1"],
                    "deliverable": "work/P2/W1.md",
                    "spawn_mode": "in_place",
                    "workers": 1,
                    "acceptance_criteria": ["b"],
                },
            ],
        },
    )
    phases = _load_plan(ctx)
    assert len(phases) == 2
    # topo 순서 — P1 먼저
    assert phases[0].id == "P1"
    assert phases[1].id == "P2"
    assert ctx.mode == "multi"
    assert ctx.command == "implement"


def test_load_plan_circular_returns_empty(tmp_path: Path) -> None:
    """순환 의존 — parse_plan_json 이 PlanLoaderError, _load_plan 은 [] 반환."""
    ctx = _make_ctx(tmp_path)
    _write_plan_json(
        ctx,
        {
            "schema_version": 2,
            "ticket": "T-1",
            "command": "research",
            "mode": "multi",
            "phases": [
                {"id": "A", "title": "", "deps": ["B"], "deliverable": "",
                 "spawn_mode": "in_place", "workers": 1, "acceptance_criteria": []},
                {"id": "B", "title": "", "deps": ["A"], "deliverable": "",
                 "spawn_mode": "in_place", "workers": 1, "acceptance_criteria": []},
            ],
        },
    )
    assert _load_plan(ctx) == []


def test_load_plan_missing_plan_json(tmp_path: Path) -> None:
    """plan.json 미존재 → []."""
    ctx = _make_ctx(tmp_path)
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
    """plan.json 미존재 시 fail_step + return False."""
    ctx = _make_ctx(tmp_path)
    result = work_step(ctx)
    assert result is False
    assert ctx.failure_md_path().exists()
    failure_text = ctx.failure_md_path().read_text(encoding="utf-8")
    assert "plan.json phases empty" in failure_text or "topo sort failed" in failure_text


def test_work_step_topo_fail_invokes_fail_step(tmp_path: Path) -> None:
    """circular dep — _load_plan [] 반환 → fail_step."""
    ctx = _make_ctx(tmp_path)
    _write_plan_json(
        ctx,
        {
            "schema_version": 2,
            "ticket": "T-1",
            "command": "research",
            "mode": "multi",
            "phases": [
                {"id": "A", "title": "", "deps": ["B"], "deliverable": "",
                 "spawn_mode": "in_place", "workers": 1, "acceptance_criteria": []},
                {"id": "B", "title": "", "deps": ["A"], "deliverable": "",
                 "spawn_mode": "in_place", "workers": 1, "acceptance_criteria": []},
            ],
        },
    )
    assert work_step(ctx) is False
    assert ctx.failure_md_path().exists()
