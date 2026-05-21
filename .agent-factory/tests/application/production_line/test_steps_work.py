"""test steps work.py — steps/work.py module testing (T-504 cutover).

T-504 cutover — write `plan/plan.json` to fixture, ` load plan` to parse plan json
Vietnamese The old YAML frontmatter inline fixture is closed.

T-506 Added: subprocess mode phase inter-level parallel (P5) + workers > 1 phase inner parallel (P6).
spawn one worker adorpatch for real claude -p subprocess launch avoidance.

Price:
  -  load plan
  -  load deps block (deps output inject / fallback when missing)
  - work_step empty phases → fail_step + return False
  - work step subprocess mode phase simultaneous spawn (P5)
  - work step workers>1 phase inner N worker simultaneous spawn (P6)
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import pytest

from engine.apps.production_line._common import WorkflowContext, write_status
from engine.apps.production_line._verify import Phase, VerifyResult
from engine.apps.production_line.stations import work as work_module
from engine.apps.production_line.stations.work import _load_deps_block, _load_plan, work_step


def _make_ctx(tmp_path: Path) -> WorkflowContext:
    (tmp_path / "work").mkdir(exist_ok=True)
    ctx = WorkflowContext(
        work_request_no="WR-489",
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
        "# plan body\\n" + "x" * 30,
        encoding="utf-8",
    )


def test_load_plan_normal(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    _write_plan_json(
        ctx,
        {
            "schema_version": 2,
            "work_request": "WR-489",
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
    # topo order — P1 first
    assert phases[0].id == "P1"
    assert phases[1].id == "P2"
    assert ctx.mode == "multi"
    assert ctx.command == "implement"


def test_load_plan_circular_returns_empty(tmp_path: Path) -> None:
    """Circulating Dependence — parse plan json This PlanLoaderError,  load plan returns []."""
    ctx = _make_ctx(tmp_path)
    _write_plan_json(
        ctx,
        {
            "schema_version": 2,
            "work_request": "WR-1",
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
    """plan.json migration → []."""
    ctx = _make_ctx(tmp_path)
    assert _load_plan(ctx) == []


def test_load_deps_block_with_deps(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    ctx.work_dir_phase_md("P1").write_text("P1 Output Body", encoding="utf-8")
    phase = Phase(id="P2", title="next", deps=["P1"])
    block = _load_deps_block(ctx, phase)
    assert "P1 Output Body" in block
    assert "work/P1.md" in block


def test_load_deps_block_no_deps(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    phase = Phase(id="P1", title="first", deps=[])
    assert _load_deps_block(ctx, phase) == "(no dependencies)"


def test_work_step_empty_phases_fails(tmp_path: Path) -> None:
    """failure step + return False."""
    ctx = _make_ctx(tmp_path)
    result = work_step(ctx)
    assert result is False
    assert ctx.failure_md_path().exists()
    failure_text = ctx.failure_md_path().read_text(encoding="utf-8")
    assert "plan.json phases empty" in failure_text or "topo sort failed" in failure_text


def test_work_step_topo_fail_invokes_fail_step(tmp_path: Path) -> None:
    """circular dep —  load plan [] return → fail step."""
    ctx = _make_ctx(tmp_path)
    _write_plan_json(
        ctx,
        {
            "schema_version": 2,
            "work_request": "WR-1",
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
# T-506 P5/P6 — subprocess mode level parallel + workers>1 phase inner parallel
# ---------------------------------------------------------------------------


def _stub_spawn_one_worker(
    monkeypatch: pytest.MonkeyPatch,
    *,
    start_record: dict[str, list[float]],
    sleep_s: float = 0.05,
    fail_phase_ids: set[str] | None = None,
) -> threading.Lock:
    """` spawn one worker` to mock — a real claude -p call syntax.

    - Create W<n>.md files in real → pass verification work md(20byte)
    - start record[phase id]
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
    """T-506 P5 — subprocess mode: level 0 of P1, P2 simultaneous spawn → P3 entry.

    P1, P2 (deps=[], subprocess) / P3 (deps=[P1, P2], subprocess).
    Simultaneous spawn verification: P1, P2 start time difference is much smaller than sleep.
    """
    ctx = _make_ctx(tmp_path)
    _write_plan_json(
        ctx,
        {
            "schema_version": 2,
            "work_request": "WR-506",
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

    # All outputs are written
    for pid in ("P1", "P2", "P3"):
        assert ctx.work_phase_w_md(pid, 1).exists()

    # P1, P2 start time difference is less than 0.05s (East spawn proof)
    p1_start = starts["P1"][0]
    p2_start = starts["P2"][0]
    assert abs(p1_start - p2_start) < 0.05, (
        f"P1, P2 not concurrent: {abs(p1_start - p2_start):.3f}s"
    )

    # P3 P1, P2 All Ended Back Start — Sleep Over 0.1s Back
    p3_start = starts["P3"][0]
    assert p3_start - max(p1_start, p2_start) >= 0.08, (
        f"P3 started before deps finished: {p3_start - max(p1_start, p2_start):.3f}s"
    )


def test_work_step_subprocess_workers_parallel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T-506 P6 — workers>1: One phase inner N worker simultaneous spawn."""
    ctx = _make_ctx(tmp_path)
    _write_plan_json(
        ctx,
        {
            "schema_version": 2,
            "work_request": "WR-506",
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

    # W1, W2, W3 output
    for n in (1, 2, 3):
        assert ctx.work_phase_w_md("P1", n).exists()

    # 3 worker simultaneous start — start time spread much smaller than sleep
    p1_starts = starts["P1"]
    assert len(p1_starts) == 3
    spread = max(p1_starts) - min(p1_starts)
    assert spread < 0.05, f"workers not concurrent: spread={spread:.3f}s"


def test_work_step_subprocess_workers_one_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T-506 P6 — workers=1 (default) → conventional single worker path (regression 0)."""
    ctx = _make_ctx(tmp_path)
    _write_plan_json(
        ctx,
        {
            "schema_version": 2,
            "work_request": "WR-506",
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
    # workers=1 → start["P1"] length 1
    assert len(starts["P1"]) == 1


def test_work_step_in_place_mode_regression(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T-506 P5 — in place mode path conservation (return 0).

    spawn mode all in place if the existing single subprocess path (parallel spawn mimic oil).
    ` run in place mode` call only one spawn with retry.
    """
    ctx = _make_ctx(tmp_path)
    _write_plan_json(
        ctx,
        {
            "schema_version": 2,
            "work_request": "WR-506",
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
    # in place is one call for work module.spawn with retry — capture argument
    calls: list[dict] = []

    def fake_spawn_with_retry(ctx, *, step, initial_prompt, system_prompt,
                               session_id, verify, artifact_path, n_max=None):
        calls.append({"step": step, "session": session_id})
        # Print
        for pid in ("P1", "P2"):
            p = ctx.work_phase_w_md(pid, 1)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("in_place mock " + "x" * 30, encoding="utf-8")
        return VerifyResult(True, []), None, 0

    monkeypatch.setattr(work_module, "spawn_with_retry", fake_spawn_with_retry)
    monkeypatch.setattr(work_module, "auto_commit", lambda ctx: 0)

    assert work_step(ctx) is True
    # Regression 0 — spawn with retry is exactly one call (two times if the subprocess mode)
    assert len(calls) == 1
    assert calls[0]["step"] == "WORK"


def test_work_step_subprocess_fail_fast_breaks_level(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T-506 P5 — fail fast (default): level 0 fail → level 1 block."""
    ctx = _make_ctx(tmp_path)
    _write_plan_json(
        ctx,
        {
            "schema_version": 2,
            "work_request": "WR-506",
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
    # P1 only starts, P2 blocks fail fast
    assert "P1" in starts
    assert "P2" not in starts
