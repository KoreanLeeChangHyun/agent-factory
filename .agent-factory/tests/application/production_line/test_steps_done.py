"""test_steps_done.py — DONE / FAILED Step wire-up (T-503 fix).

T-503 wire-up regression correction: done step / fail step by calling this write metadata
metadata.json Integrity (ex summary.txt / usage.json / failure.md and simultaneous writing).
"""

from __future__ import annotations

import json
from pathlib import Path

from engine.apps.production_line._common import WorkflowContext
from engine.apps.production_line.stations import done as done_mod


def _make_ctx(tmp_path: Path, *, command: str = "implement") -> WorkflowContext:
    work_dir = tmp_path / "runs" / "20260518-000000"
    (work_dir / "work").mkdir(parents=True, exist_ok=True)
    return WorkflowContext(
        ticket_no="T-999",
        registry_key="20260518-000000",
        work_dir=work_dir,
        command=command,
        mode="multi",
        current_step="REPORT",
        title="wire-up verification ticket",
    )


def _patch_done_externals(monkeypatch):
    monkeypatch.setattr(done_mod, "step_start", lambda *a, **k: None)
    monkeypatch.setattr(done_mod, "step_end", lambda *a, **k: None)
    monkeypatch.setattr(done_mod, "emit", lambda *a, **k: None)
    monkeypatch.setattr(done_mod, "workflow_finish", lambda *a, **k: None)
    monkeypatch.setattr(done_mod, "regression", lambda *a, **k: None)
    monkeypatch.setattr(done_mod, "kanban_move", lambda *a, **k: 0)
    monkeypatch.setattr(done_mod, "update_step", lambda *a, **k: None)

    class _FakeVerdict:
        verdict = "PASS"

        def violation_count(self) -> int:
            return 0

        def has_hard_fail(self) -> bool:
            return False

        rules: list = []

    monkeypatch.setattr(done_mod, "evaluate_12_rules", lambda ctx: _FakeVerdict())
    monkeypatch.setattr(done_mod, "save_verdict_report", lambda *a, **k: None)
    monkeypatch.setattr(
        done_mod,
        "load_template",
        lambda name: "ticket={ticket_no} key={registry_key} cmd={command} mode={mode} ts={finalized_at}"
        if name == "summary.txt"
        else "ticket={ticket_no} key={registry_key} reason={reason} ts={ts}",
    )


def test_done_step_writes_metadata_json(monkeypatch, tmp_path):
    """done step → metadata.json Integration Responsibilities + finalized at debt."""
    ctx = _make_ctx(tmp_path)
    _patch_done_externals(monkeypatch)

    done_mod.done_step(ctx)

    metadata_path = ctx.metadata_json_path()
    assert metadata_path.exists(), "metadata.json must be written by done_step"
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert payload["ticket_no"] == "T-999"
    assert payload["registry_key"] == "20260518-000000"
    assert payload["command"] == "implement"
    assert payload["finalized_at"] is not None
    assert payload["failure"] is None


def test_done_step_preserves_legacy_outputs(monkeypatch, tmp_path):
    """backward compat — summary.txt / usage.json"""
    ctx = _make_ctx(tmp_path)
    _patch_done_externals(monkeypatch)

    done_mod.done_step(ctx)

    assert ctx.summary_txt_path().exists()
    assert ctx.usage_json_path().exists()


def test_fail_step_writes_metadata_failure(monkeypatch, tmp_path):
    """fail step → metadata.json.failure field + preserve old failure.md."""
    ctx = _make_ctx(tmp_path)
    _patch_done_externals(monkeypatch)

    done_mod.fail_step(ctx, reason="phases empty")

    metadata_path = ctx.metadata_json_path()
    assert metadata_path.exists()
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert payload["failure"] is not None
    assert payload["failure"]["reason"] == "phases empty"
    assert ctx.failure_md_path().exists()
