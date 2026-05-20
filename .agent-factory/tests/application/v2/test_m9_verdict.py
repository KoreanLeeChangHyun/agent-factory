"""M9 structured verification and final verdict tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.v2._common import WorkflowContext
from engine.v2._emitter import workflow_finish
from engine.v2._validate import RuleResult, VerdictReport, save_verdict_report
from engine.v2._verdict import (
    build_final_verdict,
    get_blocking_rule_ids,
    save_final_verdict,
    write_report_manifest,
    write_verify_verdict,
)


def _ctx(tmp_path: Path, command: str = "implement") -> WorkflowContext:
    work_dir = tmp_path / "run"
    work_dir.mkdir()
    return WorkflowContext(
        ticket_no="T-900",
        registry_key="20260520-120000",
        work_dir=work_dir,
        command=command,
        title="M9 test",
    )


def _write_minimal_artifacts(ctx: WorkflowContext) -> None:
    ctx.plan_dir().mkdir(parents=True, exist_ok=True)
    ctx.plan_json_path().write_text(
        json.dumps({
            "schema_version": 1,
            "ticket": ctx.ticket_no,
            "command": ctx.command,
            "mode": "multi",
            "phases": [
                {
                    "id": "P1",
                    "title": "Build",
                    "deps": [],
                    "deliverable": "work/P1/W1.md",
                    "acceptance_criteria": ["artifact exists"],
                }
            ],
        }),
        encoding="utf-8",
    )
    ctx.plan_md_path().write_text("# Plan\n\nEnough plan body for validation.\n", encoding="utf-8")
    work_phase = ctx.work_phase_dir("P1")
    work_phase.mkdir(parents=True, exist_ok=True)
    ctx.work_phase_w_md("P1", 1).write_text("Work artifact body with enough detail.\n", encoding="utf-8")
    ctx.validate_report_md_path().write_text("Natural language quality review body.\n", encoding="utf-8")
    ctx.validate_code_json_path().parent.mkdir(parents=True, exist_ok=True)
    ctx.validate_code_json_path().write_text(
        json.dumps({
            "schema_version": 1,
            "command": "implement",
            "command_skip": False,
            "tools": [
                {"tool": "pytest", "status": "ok", "counts": {"passed": 1}},
                {"tool": "ruff", "status": "skip", "reason": "no ruff config"},
            ],
        }),
        encoding="utf-8",
    )


def test_write_verify_verdict_splits_artifact_semantic_and_code(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    _write_minimal_artifacts(ctx)

    path = write_verify_verdict(ctx)
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["stage"] == "VERIFY"
    assert payload["preliminary_verdict"] == "PASS"
    assert payload["deterministic_artifacts"][0]["name"] == "plan_artifacts"
    assert payload["semantic_evaluation"]["owner"] == "validate LLM"
    assert payload["code_checks"]["tools"][0]["tool"] == "pytest"


def test_report_manifest_links_request_plan_artifacts_and_pending_final(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    _write_minimal_artifacts(ctx)
    write_verify_verdict(ctx)
    ctx.report_html_path().write_text("<html>plan.md report</html>", encoding="utf-8")

    path = write_report_manifest(ctx)
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["stage"] == "REPORT"
    assert payload["plan"]["markdown"].endswith("plan/plan.md")
    assert payload["artifacts"]["validate_verdict"].endswith("validate/verdict.json")
    assert payload["final_decision"]["status"] == "pending_complete"


def test_final_verdict_blocks_complete_on_blocking_gate(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    report = VerdictReport(
        verdict="FAIL",
        rules=[
            RuleResult("R-CODE-1", False, detail="pytest failed"),
            RuleResult("R-CODE-2", False, detail="ruff diagnostics=2"),
        ],
    )

    payload = build_final_verdict(ctx, report)
    path = save_final_verdict(ctx, payload)
    saved = json.loads(path.read_text(encoding="utf-8"))

    assert "R-CODE-1" in get_blocking_rule_ids()
    assert saved["complete_outcome"] == "blocked"
    assert saved["blocking_failures"][0]["rule_id"] == "R-CODE-1"
    assert saved["advisory_failures"][0]["rule_id"] == "R-CODE-2"
    assert saved["workrequest_refinement"]["suggested"] is True


def test_rules_report_includes_gate_registry(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    report = VerdictReport(verdict="PASS", rules=[RuleResult("R-EXIST-1", True)])

    path = save_verdict_report(ctx, report)
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["gate_registry"]
    assert any(g["rule_id"] == "R-EXIST-1" and g["severity"] == "blocking" for g in payload["gate_registry"])


def test_workflow_finish_posts_final_verdict_extras_for_refinement(tmp_path: Path, monkeypatch) -> None:
    ctx = _ctx(tmp_path)
    ctx.wf_session_id = "wf-T-900-test"
    posted: list[tuple[str, dict]] = []

    monkeypatch.setattr("engine.v2._emitter._post_to_board", lambda endpoint, body: posted.append((endpoint, body)))

    workflow_finish(
        ctx,
        outcome="fail",
        verdict="FAIL",
        summary="blocked",
        final_verdict_path=str(ctx.final_verdict_json_path()),
        workrequest_refinement={"suggested": True, "ticket": ctx.ticket_no},
    )

    assert posted[0][0].endswith("/api/v2/sessions/wf-T-900-test/finish")
    assert posted[0][1]["outcome"] == "fail"
    assert posted[0][1]["final_verdict_path"].endswith("final-verdict.json")
    assert posted[0][1]["workrequest_refinement"]["suggested"] is True
