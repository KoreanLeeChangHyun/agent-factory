"""test_steps_validate.py — VALIDATE Step wire-up (T-503 fix).

T-503 wire-up regression correction: validate step (1)  verify code.run(ctx) call →
validate/code.json output (2) validate/report.md nested mirror creation (3)
Business nested output inject with md regression matching.
"""

from __future__ import annotations

from pathlib import Path

from engine.apps.production_line._common import WorkflowContext
from engine.apps.production_line.stations import validate as validate_mod


def _make_ctx(tmp_path: Path, *, command: str = "implement") -> WorkflowContext:
    work_dir = tmp_path / "runs" / "20260518-000000"
    (work_dir / "work").mkdir(parents=True, exist_ok=True)
    # T-504 cutover — plan/plan.md (nested) pre-curtain
    (work_dir / "plan").mkdir(parents=True, exist_ok=True)
    (work_dir / "plan" / "plan.md").write_text("plan body\n", encoding="utf-8")
    ctx = WorkflowContext(
        ticket_no="T-999",
        registry_key="20260518-000000",
        work_dir=work_dir,
        command=command,
        mode="multi",
        current_step="WORK",
        title="wire-up verification",
    )
    return ctx


def _patch_validate_externals(monkeypatch, *, simulate_llm_artifact: bool = True):
    """LLM spawn moking — Simulation of creation of artifact files."""
    captured = {"verify_code_called": 0}

    def fake_spawn_with_retry(ctx, *, step, artifact_path, **kw):
        if simulate_llm_artifact:
            Path(artifact_path).parent.mkdir(parents=True, exist_ok=True)
            Path(artifact_path).write_text("validate report body\n", encoding="utf-8")

    def fake_verify_run(ctx):
        captured["verify_code_called"] += 1
        path = ctx.validate_code_json_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"tools": []}', encoding="utf-8")
        return path

    monkeypatch.setattr(validate_mod, "spawn_with_retry", fake_spawn_with_retry)
    monkeypatch.setattr(validate_mod, "write_context", lambda *a, **k: None)
    monkeypatch.setattr(validate_mod, "load_prompt", lambda name: "system prompt")
    monkeypatch.setattr(validate_mod, "append_log", lambda *a, **k: None)
    monkeypatch.setattr(validate_mod._verify_code, "run", fake_verify_run)
    return captured


def test_validate_step_invokes_verify_code(monkeypatch, tmp_path):
    """validate step →  verify code.run(ctx) call + validate/code.json output."""
    ctx = _make_ctx(tmp_path, command="implement")
    captured = _patch_validate_externals(monkeypatch)

    validate_mod.validate_step(ctx)

    assert captured["verify_code_called"] == 1
    assert ctx.validate_code_json_path().exists()


def test_validate_step_writes_nested_report_mirror(monkeypatch, tmp_path):
    """validate step → validate/report.md (nested) simultaneous creation (document mig)."""
    ctx = _make_ctx(tmp_path)
    _patch_validate_externals(monkeypatch)

    validate_mod.validate_step(ctx)

    flat_report = ctx.validate_report_md_path()
    nested_report = ctx.validate_report_md_nested_path()
    assert flat_report.exists()
    assert nested_report.exists()
    assert nested_report.read_text(encoding="utf-8") == flat_report.read_text(encoding="utf-8")


def test_validate_step_globs_nested_work_md(monkeypatch, tmp_path):
    """Business md recurring — nested work/<phase>/W1.md also inject."""
    ctx = _make_ctx(tmp_path)
    nested_md = ctx.work_phase_w_md("P1", 1)
    nested_md.parent.mkdir(parents=True, exist_ok=True)
    nested_md.write_text("P1 W1 body\n", encoding="utf-8")
    flat_md = ctx.work_dir_phase_md("P2")
    flat_md.parent.mkdir(parents=True, exist_ok=True)
    flat_md.write_text("P2 flat body\n", encoding="utf-8")

    captured = {"prompt": ""}

    def fake_spawn_with_retry(ctx, *, initial_prompt, artifact_path, **kw):
        captured["prompt"] = initial_prompt
        Path(artifact_path).parent.mkdir(parents=True, exist_ok=True)
        Path(artifact_path).write_text("validate body\n", encoding="utf-8")

    monkeypatch.setattr(validate_mod, "spawn_with_retry", fake_spawn_with_retry)
    monkeypatch.setattr(validate_mod, "write_context", lambda *a, **k: None)
    monkeypatch.setattr(validate_mod, "load_prompt", lambda name: "system prompt")
    monkeypatch.setattr(validate_mod, "append_log", lambda *a, **k: None)
    monkeypatch.setattr(validate_mod._verify_code, "run", lambda ctx: None)

    validate_mod.validate_step(ctx)

    assert "P1 W1 body" in captured["prompt"]
    assert "P2 flat body" in captured["prompt"]
    assert "P1/W1.md" in captured["prompt"]
    assert "P2.md" in captured["prompt"]
