"""Tests for core validation artifact rules."""

from __future__ import annotations

import json
from pathlib import Path

from engine.core.validation.artifact_rules import (
    VerifyResult,
    verify_artifact,
    verify_plan_artifacts,
    verify_report_html,
)


def _good_plan_payload() -> dict:
    return {
        "schema_version": 2,
        "work_request": "WR-504",
        "command": "implement",
        "mode": "multi",
        "phases": [
            {
                "id": "P1",
                "title": "first",
                "deps": [],
                "deliverable": "work/P1/W1.md",
                "spawn_mode": "in_place",
                "workers": 1,
                "acceptance_criteria": ["x"],
            }
        ],
    }


def test_verify_result_merge_combines_state_and_missing() -> None:
    result = VerifyResult(True).merge(VerifyResult(False, ["missing artifact"]))

    assert not result.ok
    assert result.missing == ["missing artifact"]


def test_verify_artifact_checks_required_tokens(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact.md"
    artifact.write_text("created from plan.md", encoding="utf-8")

    ok = verify_artifact(artifact, must_contain=("plan.md",))
    failed = verify_artifact(artifact, must_contain=("report.html",))

    assert ok.ok
    assert not failed.ok
    assert failed.missing == ["missing token 'report.html' in artifact.md"]


def test_verify_plan_artifacts_checks_schema(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    (plan_dir / "plan.json").write_text(
        json.dumps(_good_plan_payload()), encoding="utf-8"
    )
    (plan_dir / "plan.md").write_text("plan body " * 8, encoding="utf-8")

    assert verify_plan_artifacts(plan_dir / "plan.json", plan_dir / "plan.md").ok

    bad = _good_plan_payload()
    bad["phases"] = []
    (plan_dir / "plan.json").write_text(json.dumps(bad), encoding="utf-8")

    result = verify_plan_artifacts(plan_dir / "plan.json", plan_dir / "plan.md")
    assert not result.ok
    assert any("schema error" in message for message in result.missing)


def test_verify_report_html_requires_plan_reference(tmp_path: Path) -> None:
    report = tmp_path / "report.html"
    plan = tmp_path / "plan" / "plan.md"
    plan.parent.mkdir()
    plan.write_text("plan body", encoding="utf-8")

    report.write_text(
        "<html><body>report links plan.md</body></html>" + "x" * 50,
        encoding="utf-8",
    )
    assert verify_report_html(report, plan).ok

    report.write_text("<html><body>missing reference</body></html>" + "x" * 50)
    result = verify_report_html(report, plan)
    assert not result.ok
    assert result.missing == ["missing token 'plan.md' in report.html"]
