"""WR-513 P1 — driver fail step thread (SPEC.md §12.4 static).

support criteria #4 — "driver fail step"
Operating threads. SPEC.md §12.4 + feedback no speculative guards 2026-05-08 according to the rule
Actually adopted policy "conveyor automatic revolving X" (auto regression OFF). The test is that
Testimonials NEWS

  - status.json workflow phase → FAILED
  - failure.md write
  - metadata.json failure field
  - conveyor move NOT call (automatic regression X — Open regression only user licence trigger)
  - Preserving worktree directory (Auto Cleanup X)

<# if ( data.meta.album ) { #>{{ data.meta.album }}<# } #> Unit testing only — using monkeypatch + tempfile.
"""

from __future__ import annotations

import json
from pathlib import Path

from engine.apps.production_line._common import WorkflowContext
from engine.apps.production_line.stations import done as done_mod


def _make_ctx(tmp_path: Path) -> WorkflowContext:
    work_dir = tmp_path / "runs" / "20260520-000000"
    (work_dir / "work").mkdir(parents=True, exist_ok=True)
    worktree_dir = tmp_path / "worktrees" / "feat-WR-513-test"
    worktree_dir.mkdir(parents=True, exist_ok=True)
    sentinel = worktree_dir / "sentinel.txt"
    sentinel.write_text("preserve me", encoding="utf-8")
    return WorkflowContext(
        work_request_no="WR-513",
        registry_key="20260520-000000",
        work_dir=work_dir,
        command="implement",
        mode="multi",
        current_step="WORK",
        feature_branch="feat/WR-513-test",
        worktree_path=worktree_dir,
        title="fail step",
    )


def _patch_externals(monkeypatch, conveyor_calls: list, finish_calls: list) -> None:
    monkeypatch.setattr(
        done_mod,
        "load_template",
        lambda name: (
            "work_request={work_request_no} key={registry_key} reason={reason} ts={ts}"
        ),
    )
    monkeypatch.setattr(
        done_mod,
        "conveyor_move",
        lambda *args, **kwargs: conveyor_calls.append(args) or 0,
    )
    monkeypatch.setattr(done_mod, "regression", lambda *a, **k: None)
    monkeypatch.setattr(
        done_mod,
        "workflow_finish",
        lambda *a, **k: finish_calls.append((a, k)),
    )
    # update step maintains the original to write status.json


def test_fail_step_status_json_workflow_phase_failed(monkeypatch, tmp_path):
    """fail step → status.json workflow phase=FAILED reaches."""
    ctx = _make_ctx(tmp_path)
    _patch_externals(monkeypatch, [], [])

    done_mod.fail_step(ctx, reason="WORK Step forced failure")

    status_path = ctx.status_json_path()
    assert status_path.exists()
    status = json.loads(status_path.read_text(encoding="utf-8"))
    assert status["workflow_step"] == "FAILED"
    transitions = status["transitions"]
    assert len(transitions) >= 1
    last = transitions[-1]
    assert last["to"] == "FAILED"
    assert last["note"] == "WORK Step forced failure"


def test_fail_step_writes_failure_md(monkeypatch, tmp_path):
    """fail step → failure.md write + reason text included."""
    ctx = _make_ctx(tmp_path)
    _patch_externals(monkeypatch, [], [])

    done_mod.fail_step(ctx, reason="phases empty")

    failure_path = ctx.failure_md_path()
    assert failure_path.exists()
    assert "phases empty" in failure_path.read_text(encoding="utf-8")


def test_fail_step_metadata_failure_field(monkeypatch, tmp_path):
    """fail step → metadata.json failure field debt (reason + ts)."""
    ctx = _make_ctx(tmp_path)
    _patch_externals(monkeypatch, [], [])

    done_mod.fail_step(ctx, reason="subprocess timeout")

    metadata_path = ctx.metadata_json_path()
    assert metadata_path.exists()
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert payload["failure"] is not None
    assert payload["failure"]["reason"] == "subprocess timeout"
    assert "ts" in payload["failure"]


def test_fail_step_does_not_auto_regress_conveyor(monkeypatch, tmp_path):
    """fail step → conveyor move call 0 (Automatic Regression X — SPEC.md §12.4)."""
    ctx = _make_ctx(tmp_path)
    conveyor_calls: list = []
    _patch_externals(monkeypatch, conveyor_calls, [])

    done_mod.fail_step(ctx, reason="auto regression off check")

    assert conveyor_calls == [], (
        "fail step call conveyor move —"
        "feedback no speculative guards 2026-05-08 + SPEC.md §12.4 Formulation"
    )


def test_fail_step_preserves_worktree(monkeypatch, tmp_path):
    """fail step → ctx.worktree path Director + Output Retention (Auto Clear X)."""
    ctx = _make_ctx(tmp_path)
    _patch_externals(monkeypatch, [], [])
    assert ctx.worktree_path is not None
    sentinel = ctx.worktree_path / "sentinel.txt"

    done_mod.fail_step(ctx, reason="worktree preservation check")

    assert ctx.worktree_path.exists(), (
        "fail step Automatically delete this worktree directory"
    )
    assert sentinel.exists(), "worktree inner output"
    assert sentinel.read_text(encoding="utf-8") == "preserve me"


def test_fail_step_emits_workflow_finish_fail(monkeypatch, tmp_path):
    """Failure step → workflow finish(outcome='fail', verdict='FAIL')"""
    ctx = _make_ctx(tmp_path)
    finish_calls: list = []
    _patch_externals(monkeypatch, [], finish_calls)

    done_mod.fail_step(ctx, reason="finish emit check")

    assert len(finish_calls) == 1
    args, kwargs = finish_calls[0]
    assert kwargs.get("outcome") == "fail"
    assert kwargs.get("verdict") == "FAIL"
