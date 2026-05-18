"""test_common.py — _common.py 단위 테스트.

대상:
  - WorkflowContext path 헬퍼 (8 메서드)
  - new_registry_key 형식
  - read_status / write_status / update_step (status.json I/O)
  - write_context / read_context (.context.json)
  - load_prompt / load_template
  - WORKFLOW_STEPS / TERMINAL_STEPS / N_MAX_BY_STEP / STEP_TIMEOUT_BY_STEP 상수
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import pytest

from engine.v2._common import (
    N_MAX_BY_STEP,
    PROMPTS_DIR,
    STEP_TIMEOUT_BY_STEP,
    TEMPLATES_DIR,
    TERMINAL_STEPS,
    WORKFLOW_STEPS,
    WorkflowContext,
    load_prompt,
    load_template,
    make_work_dir,
    new_registry_key,
    read_context,
    read_metadata,
    read_status,
    update_step,
    write_context,
    write_metadata,
    write_status,
)


def _make_ctx(tmp_path: Path) -> WorkflowContext:
    return WorkflowContext(
        ticket_no="T-489",
        registry_key="20260515-000000",
        work_dir=tmp_path,
        command="implement",
        mode="multi",
        current_step="INIT",
    )


def test_workflow_steps_canon() -> None:
    assert WORKFLOW_STEPS == (
        "NONE", "INIT", "PLAN", "WORK", "VALIDATE", "REPORT", "DONE", "FAILED",
    )
    assert TERMINAL_STEPS == ("DONE", "FAILED")


def test_n_max_canon() -> None:
    # SPEC.md §3.4
    assert N_MAX_BY_STEP == {
        "INIT": 0, "PLAN": 2, "WORK": 3, "VALIDATE": 1, "REPORT": 2, "DONE": 0,
    }


def test_step_timeout_canon() -> None:
    # SPEC.md §8.1
    assert STEP_TIMEOUT_BY_STEP == {"PLAN": 300, "WORK": 1800, "VALIDATE": 180, "REPORT": 600}


def test_new_registry_key_format() -> None:
    key = new_registry_key()
    assert re.fullmatch(r"\d{8}-\d{6}", key)


def test_new_registry_key_custom_datetime() -> None:
    dt = datetime(2026, 5, 15, 12, 34, 56)
    assert new_registry_key(dt) == "20260515-123456"


def test_workflow_context_paths(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    assert ctx.status_json_path() == tmp_path / "status.json"
    assert ctx.context_json_path() == tmp_path / ".context.json"
    assert ctx.metrics_jsonl_path() == tmp_path / "metrics.jsonl"
    assert ctx.workflow_log_path() == tmp_path / "workflow.log"
    assert ctx.plan_md_path() == tmp_path / "plan.md"
    assert ctx.work_dir_phase_md("P1") == tmp_path / "work" / "P1.md"
    assert ctx.validate_report_md_path() == tmp_path / "validate-report.md"
    assert ctx.report_md_path() == tmp_path / "report.md"
    assert ctx.user_prompt_path() == tmp_path / "user_prompt.txt"
    assert ctx.summary_txt_path() == tmp_path / "summary.txt"
    assert ctx.usage_json_path() == tmp_path / "usage.json"
    assert ctx.failure_md_path() == tmp_path / "failure.md"


def test_status_io_roundtrip(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    # 초기 read — 파일 없으면 default
    s0 = read_status(ctx)
    assert s0 == {"workflow_step": "NONE", "transitions": []}
    # write + read
    write_status(ctx, {"workflow_step": "INIT", "transitions": []})
    s1 = read_status(ctx)
    assert s1["workflow_step"] == "INIT"


def test_update_step_transitions(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    write_status(ctx, {"workflow_step": "INIT", "transitions": []})
    update_step(ctx, "INIT", "PLAN", note="advance")
    s = read_status(ctx)
    assert s["workflow_step"] == "PLAN"
    assert len(s["transitions"]) == 1
    assert s["transitions"][0]["from"] == "INIT"
    assert s["transitions"][0]["to"] == "PLAN"
    assert s["transitions"][0]["note"] == "advance"
    assert ctx.current_step == "PLAN"


def test_update_step_invalid_target(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    write_status(ctx, {"workflow_step": "NONE", "transitions": []})
    with pytest.raises(ValueError):
        update_step(ctx, "NONE", "BOGUS_STEP")


def test_context_io_roundtrip(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    ctx.feature_branch = "feat/T-489"
    ctx.worktree_path = Path("/tmp/wt/feat-T-489")
    ctx.title = "샘플 티켓 제목"
    ctx.session_ids["wf-T489-PLAN"] = "abc-uuid"
    write_context(ctx)
    payload = read_context(ctx)
    assert payload["schema_version"] == 1
    assert payload["ticket_no"] == "T-489"
    assert payload["engine_version"] == "v2"
    assert payload["feature_branch"] == "feat/T-489"
    assert payload["worktree_path"] == "/tmp/wt/feat-T-489"
    assert payload["title"] == "샘플 티켓 제목"
    assert payload["session_ids"]["wf-T489-PLAN"] == "abc-uuid"


def test_context_io_worktree_less(tmp_path: Path) -> None:
    """worktree_path=None → JSON 직렬화 시 null."""
    ctx = _make_ctx(tmp_path)
    ctx.feature_branch = None
    write_context(ctx)
    payload = read_context(ctx)
    assert payload["worktree_path"] is None
    assert payload["feature_branch"] is None
    assert payload["title"] == ""


def test_make_work_dir_creates_work_subdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # RUNS_DIR redirect
    from engine.v2 import _common
    monkeypatch.setattr(_common, "RUNS_DIR", tmp_path / "runs")
    work_dir = make_work_dir("20260515-000000")
    assert work_dir.exists()
    assert (work_dir / "work").exists()


def test_load_prompt_all_under_10kb_cap() -> None:
    for name in ("plan", "work", "validate", "report"):
        text = load_prompt(name)
        assert len(text) > 100, f"{name} too small"
        # SPEC.md §8.3 — 10KB cap
        assert len(text) <= 10_000, f"{name} exceeds 10KB cap: {len(text)}"


def test_load_template_existence() -> None:
    for name in ("retry_prompt.txt", "summary.txt", "failure.md"):
        text = load_template(name)
        assert text.strip()


def test_prompts_and_templates_dir_exist() -> None:
    assert PROMPTS_DIR.exists()
    assert TEMPLATES_DIR.exists()
    assert (PROMPTS_DIR / "plan.txt").exists()
    assert (TEMPLATES_DIR / "retry_prompt.txt").exists()


# -------- T-503 신설 path helpers --------


def test_work_phase_dir(tmp_path: Path) -> None:
    """T-503 — work_phase_dir(phase_id) → work/<phase>/ 디렉터리 path."""
    ctx = _make_ctx(tmp_path)
    assert ctx.work_phase_dir("P1") == tmp_path / "work" / "P1"
    assert ctx.work_phase_dir("P42") == tmp_path / "work" / "P42"


def test_work_phase_w_md(tmp_path: Path) -> None:
    """T-503 — work_phase_w_md(phase_id, worker_idx) → work/<phase>/W<n>.md."""
    ctx = _make_ctx(tmp_path)
    assert ctx.work_phase_w_md("P1") == tmp_path / "work" / "P1" / "W1.md"
    assert ctx.work_phase_w_md("P1", 1) == tmp_path / "work" / "P1" / "W1.md"
    assert ctx.work_phase_w_md("P2", 3) == tmp_path / "work" / "P2" / "W3.md"


def test_work_phase_md_resolved_nested_priority(tmp_path: Path) -> None:
    """T-503 — nested 존재 시 nested 우선."""
    ctx = _make_ctx(tmp_path)
    nested = ctx.work_phase_w_md("P1", 1)
    flat = ctx.work_dir_phase_md("P1")
    nested.parent.mkdir(parents=True, exist_ok=True)
    nested.write_text("nested", encoding="utf-8")
    flat.parent.mkdir(parents=True, exist_ok=True)
    flat.write_text("flat", encoding="utf-8")
    resolved = ctx.work_phase_md_resolved("P1")
    assert resolved == nested


def test_work_phase_md_resolved_flat_fallback(tmp_path: Path) -> None:
    """T-503 — nested 미존재 + flat 존재 → flat fallback."""
    ctx = _make_ctx(tmp_path)
    flat = ctx.work_dir_phase_md("P1")
    flat.parent.mkdir(parents=True, exist_ok=True)
    flat.write_text("flat", encoding="utf-8")
    resolved = ctx.work_phase_md_resolved("P1")
    assert resolved == flat


def test_work_phase_md_resolved_neither_returns_nested_default(tmp_path: Path) -> None:
    """T-503 — 양쪽 미존재 → nested 기본 경로 반환 (write-target 으로 사용 가능)."""
    ctx = _make_ctx(tmp_path)
    resolved = ctx.work_phase_md_resolved("P1")
    assert resolved == ctx.work_phase_w_md("P1", 1)
    assert not resolved.exists()


def test_validate_dir(tmp_path: Path) -> None:
    """T-503 — validate/ 디렉터리 path."""
    ctx = _make_ctx(tmp_path)
    assert ctx.validate_dir() == tmp_path / "validate"


def test_validate_nested_paths(tmp_path: Path) -> None:
    """T-503 — validate/report.md / validate/rules.json / validate/code.json."""
    ctx = _make_ctx(tmp_path)
    assert ctx.validate_report_md_nested_path() == tmp_path / "validate" / "report.md"
    assert ctx.validate_rules_json_nested_path() == tmp_path / "validate" / "rules.json"
    assert ctx.validate_code_json_path() == tmp_path / "validate" / "code.json"


def test_flat_paths_preserved_for_backward_compat(tmp_path: Path) -> None:
    """T-503 — 옛 flat path helpers (`validate-report.md` 등) 보존 (backward compat)."""
    ctx = _make_ctx(tmp_path)
    assert ctx.validate_report_md_path() == tmp_path / "validate-report.md"
    assert ctx.validate_rules_json_path() == tmp_path / "validate-rules.json"
    assert ctx.failure_md_path() == tmp_path / "failure.md"
    assert ctx.summary_txt_path() == tmp_path / "summary.txt"


def test_metadata_json_path(tmp_path: Path) -> None:
    """T-503 — metadata.json path."""
    ctx = _make_ctx(tmp_path)
    assert ctx.metadata_json_path() == tmp_path / "metadata.json"


# -------- T-503 write_metadata / read_metadata --------


def test_write_metadata_basic(tmp_path: Path) -> None:
    """T-503 — metadata.json 통합 writer. 옛 4 파일 (.context.json + status.json + summary.txt + failure.md) 흡수."""
    ctx = _make_ctx(tmp_path)
    ctx.feature_branch = "feat/T-503"
    ctx.title = "T-503 시범"
    ctx.session_ids["wf-T503-PLAN"] = "uuid-1"
    write_status(ctx, {"workflow_step": "DONE", "transitions": [{"from": "INIT", "to": "PLAN"}]})
    path = write_metadata(ctx, finalized_at="2026-05-18T23:59:59")
    assert path == ctx.metadata_json_path()
    assert path.exists()
    import json as _json
    payload = _json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["ticket_no"] == "T-489"
    assert payload["feature_branch"] == "feat/T-503"
    assert payload["title"] == "T-503 시범"
    assert payload["session_ids"]["wf-T503-PLAN"] == "uuid-1"
    assert payload["workflow_step"] == "DONE"
    assert len(payload["transitions"]) == 1
    assert payload["finalized_at"] == "2026-05-18T23:59:59"
    assert payload["failure"] is None


def test_write_metadata_failure(tmp_path: Path) -> None:
    """T-503 — failure_reason 박제 시 failure 필드에 reason + ts."""
    ctx = _make_ctx(tmp_path)
    write_status(ctx, {"workflow_step": "FAILED", "transitions": []})
    path = write_metadata(ctx, failure_reason="plan.md not produced after retries")
    import json as _json
    payload = _json.loads(path.read_text(encoding="utf-8"))
    assert payload["workflow_step"] == "FAILED"
    assert payload["failure"]["reason"] == "plan.md not produced after retries"
    assert "ts" in payload["failure"]


def test_read_metadata_missing(tmp_path: Path) -> None:
    """T-503 — metadata.json 미존재 시 `{}` 반환."""
    ctx = _make_ctx(tmp_path)
    assert read_metadata(ctx) == {}


def test_read_metadata_present(tmp_path: Path) -> None:
    """T-503 — metadata.json 존재 시 dict 반환."""
    ctx = _make_ctx(tmp_path)
    write_status(ctx, {"workflow_step": "DONE", "transitions": []})
    write_metadata(ctx, finalized_at="2026-05-18T00:00:00")
    payload = read_metadata(ctx)
    assert payload["workflow_step"] == "DONE"
    assert payload["finalized_at"] == "2026-05-18T00:00:00"
