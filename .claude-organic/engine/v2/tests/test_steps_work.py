"""test_steps_work.py — steps/work.py 단위 테스트 (T-504 cutover).

T-504 cutover — `plan/plan.json` 을 fixture 로 작성, `_load_plan` 이 parse_plan_json
경유. 옛 YAML frontmatter inline fixture 통째 폐기.

T-506 추가: subprocess 모드 phase 간 level 병렬 (P5) + workers > 1 phase 안 병렬 (P6).
실제 claude -p subprocess 발사 회피 위해 _spawn_one_worker 를 monkeypatch.

대상:
  - _load_plan (plan.json 정합 / 미존재 / circular dep → [])
  - _load_deps_block (deps 산출물 inject / 없을 때 fallback)
  - work_step empty phases → fail_step + return False
  - work_step subprocess 모드 phase 간 level 동시 spawn (P5)
  - work_step workers>1 phase 안 N worker 동시 spawn (P6)
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import pytest

from engine.v2._common import WorkflowContext, write_status
from engine.v2._verify import Phase, VerifyResult
from engine.v2.steps import work as work_module
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


# ---------------------------------------------------------------------------
# T-506 P5/P6 — subprocess 모드 level 병렬 + workers>1 phase 안 병렬
# ---------------------------------------------------------------------------


def _stub_spawn_one_worker(
    monkeypatch: pytest.MonkeyPatch,
    *,
    start_record: dict[str, list[float]],
    sleep_s: float = 0.05,
    fail_phase_ids: set[str] | None = None,
) -> threading.Lock:
    """`_spawn_one_worker` 를 mock — 실제 claude -p 호출 회피.

    - W<n>.md 파일을 실제로 작성 → verify_work_md(20byte) 통과
    - start_record[phase_id] 에 호출 시작 시간 누적 (동시 spawn 검증용)
    """
    lock = threading.Lock()
    fail_phase_ids = fail_phase_ids or set()

    def fake(ctx: WorkflowContext, phase: Phase, worker_idx: int, **kwargs):
        artifact = ctx.work_phase_w_md(phase.id, worker_idx)
        artifact.parent.mkdir(parents=True, exist_ok=True)
        with lock:
            start_record.setdefault(phase.id, []).append(time.monotonic())
        time.sleep(sleep_s)
        artifact.write_text(
            f"# mock W{worker_idx}.md for {phase.id}\n" + "x" * 30,
            encoding="utf-8",
        )
        fake_session = f"mock-session-{phase.id}-W{worker_idx}"
        if phase.id in fail_phase_ids:
            return VerifyResult(False, [f"forced fail {phase.id}"]), fake_session
        return VerifyResult(True, []), fake_session

    monkeypatch.setattr(work_module, "_spawn_one_worker", fake)
    return lock


def test_work_step_subprocess_level_parallel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T-506 P5 — subprocess 모드: level 0 의 P1, P2 동시 spawn → P3 진입.

    P1, P2 (deps=[], subprocess) / P3 (deps=[P1, P2], subprocess).
    동시 spawn 검증: P1, P2 시작 시간 차이가 sleep 보다 훨씬 작음.
    """
    ctx = _make_ctx(tmp_path)
    _write_plan_json(
        ctx,
        {
            "schema_version": 2,
            "ticket": "T-506",
            "command": "implement",
            "mode": "multi",
            "phases": [
                {"id": "P1", "title": "a", "deps": [], "deliverable": "work/P1/W1.md",
                 "spawn_mode": "subprocess", "workers": 1, "acceptance_criteria": ["a"]},
                {"id": "P2", "title": "b", "deps": [], "deliverable": "work/P2/W1.md",
                 "spawn_mode": "subprocess", "workers": 1, "acceptance_criteria": ["b"]},
                {"id": "P3", "title": "c", "deps": ["P1", "P2"],
                 "deliverable": "work/P3/W1.md", "spawn_mode": "subprocess",
                 "workers": 1, "acceptance_criteria": ["c"]},
            ],
        },
    )
    starts: dict[str, list[float]] = {}
    _stub_spawn_one_worker(monkeypatch, start_record=starts, sleep_s=0.1)
    monkeypatch.setattr(work_module, "auto_commit", lambda ctx: 0)

    assert work_step(ctx) is True

    # 모든 산출물 작성됨
    for pid in ("P1", "P2", "P3"):
        assert ctx.work_phase_w_md(pid, 1).exists()

    # P1, P2 시작 시간 차이가 0.05s 미만 (동시 spawn 증거)
    p1_start = starts["P1"][0]
    p2_start = starts["P2"][0]
    assert abs(p1_start - p2_start) < 0.05, (
        f"P1, P2 not concurrent: {abs(p1_start - p2_start):.3f}s"
    )

    # P3 는 P1, P2 모두 끝난 뒤 시작 — sleep 0.1s 이상 뒤
    p3_start = starts["P3"][0]
    assert p3_start - max(p1_start, p2_start) >= 0.08, (
        f"P3 started before deps finished: {p3_start - max(p1_start, p2_start):.3f}s"
    )


def test_work_step_subprocess_workers_parallel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T-506 P6 — workers>1: 한 phase 안 N worker 동시 spawn."""
    ctx = _make_ctx(tmp_path)
    _write_plan_json(
        ctx,
        {
            "schema_version": 2,
            "ticket": "T-506",
            "command": "implement",
            "mode": "multi",
            "phases": [
                {"id": "P1", "title": "multi-worker", "deps": [],
                 "deliverable": "work/P1/W1.md", "spawn_mode": "subprocess",
                 "workers": 3, "acceptance_criteria": ["a"]},
            ],
        },
    )
    starts: dict[str, list[float]] = {}
    _stub_spawn_one_worker(monkeypatch, start_record=starts, sleep_s=0.1)
    monkeypatch.setattr(work_module, "auto_commit", lambda ctx: 0)

    assert work_step(ctx) is True

    # W1, W2, W3 산출물 모두 작성됨
    for n in (1, 2, 3):
        assert ctx.work_phase_w_md("P1", n).exists()

    # 3 worker 동시 시작 — start 시간 spread 가 sleep 보다 훨씬 작음
    p1_starts = starts["P1"]
    assert len(p1_starts) == 3
    spread = max(p1_starts) - min(p1_starts)
    assert spread < 0.05, f"workers not concurrent: spread={spread:.3f}s"


def test_work_step_subprocess_workers_one_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T-506 P6 — workers=1 (default) → 기존 단일 worker 경로 (회귀 0)."""
    ctx = _make_ctx(tmp_path)
    _write_plan_json(
        ctx,
        {
            "schema_version": 2,
            "ticket": "T-506",
            "command": "implement",
            "mode": "multi",
            "phases": [
                {"id": "P1", "title": "single", "deps": [],
                 "deliverable": "work/P1/W1.md", "spawn_mode": "subprocess",
                 "workers": 1, "acceptance_criteria": ["a"]},
            ],
        },
    )
    starts: dict[str, list[float]] = {}
    _stub_spawn_one_worker(monkeypatch, start_record=starts, sleep_s=0.02)
    monkeypatch.setattr(work_module, "auto_commit", lambda ctx: 0)

    assert work_step(ctx) is True
    assert ctx.work_phase_w_md("P1", 1).exists()
    # workers=1 → starts["P1"] 길이 1
    assert len(starts["P1"]) == 1


def test_work_step_in_place_mode_regression(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T-506 P5 — in_place 모드 경로 보존 (회귀 0).

    spawn_mode 모두 in_place 면 기존 단일 subprocess 경로 (parallel_spawn 미경유).
    `_run_in_place_mode` 가 spawn_with_retry 1회만 호출.
    """
    ctx = _make_ctx(tmp_path)
    _write_plan_json(
        ctx,
        {
            "schema_version": 2,
            "ticket": "T-506",
            "command": "implement",
            "mode": "multi",
            "phases": [
                {"id": "P1", "title": "a", "deps": [],
                 "deliverable": "work/P1/W1.md", "spawn_mode": "in_place",
                 "workers": 1, "acceptance_criteria": ["a"]},
                {"id": "P2", "title": "b", "deps": ["P1"],
                 "deliverable": "work/P2/W1.md", "spawn_mode": "in_place",
                 "workers": 1, "acceptance_criteria": ["b"]},
            ],
        },
    )
    # in_place 는 work_module.spawn_with_retry 1회 호출 — 인자 캡처
    calls: list[dict] = []

    def fake_spawn_with_retry(ctx, *, step, initial_prompt, system_prompt,
                               session_id, verify, artifact_path, n_max=None):
        calls.append({"step": step, "session": session_id})
        # 산출물 작성
        for pid in ("P1", "P2"):
            p = ctx.work_phase_w_md(pid, 1)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("in_place mock " + "x" * 30, encoding="utf-8")
        return VerifyResult(True, []), None, 0

    monkeypatch.setattr(work_module, "spawn_with_retry", fake_spawn_with_retry)
    monkeypatch.setattr(work_module, "auto_commit", lambda ctx: 0)

    assert work_step(ctx) is True
    # 회귀 0 — spawn_with_retry 가 정확히 1회 호출됨 (subprocess 모드 였다면 2회)
    assert len(calls) == 1
    assert calls[0]["step"] == "WORK"


def test_work_step_subprocess_fail_fast_breaks_level(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T-506 P5 — fail_fast (default): level 0 fail → level 1 진입 차단."""
    ctx = _make_ctx(tmp_path)
    _write_plan_json(
        ctx,
        {
            "schema_version": 2,
            "ticket": "T-506",
            "command": "implement",
            "mode": "multi",
            "phases": [
                {"id": "P1", "title": "fails", "deps": [],
                 "deliverable": "work/P1/W1.md", "spawn_mode": "subprocess",
                 "workers": 1, "acceptance_criteria": ["a"]},
                {"id": "P2", "title": "after", "deps": ["P1"],
                 "deliverable": "work/P2/W1.md", "spawn_mode": "subprocess",
                 "workers": 1, "acceptance_criteria": ["b"]},
            ],
        },
    )
    starts: dict[str, list[float]] = {}
    _stub_spawn_one_worker(
        monkeypatch, start_record=starts, sleep_s=0.02,
        fail_phase_ids={"P1"},
    )
    monkeypatch.setattr(work_module, "auto_commit", lambda ctx: 0)
    monkeypatch.setenv("V2_FAIL_POLICY", "fail_fast")

    work_step(ctx)
    # P1 만 시작, P2 는 fail_fast 로 차단
    assert "P1" in starts
    assert "P2" not in starts
