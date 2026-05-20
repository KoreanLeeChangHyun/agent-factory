"""Tests for REPORT-stage prompt construction."""

from __future__ import annotations

from pathlib import Path

from engine.application.reporting.prompt import (
    ReportPromptInput,
    build_report_initial_prompt,
)


def test_build_report_initial_prompt_includes_all_artifact_inputs() -> None:
    prompt = build_report_initial_prompt(
        ReportPromptInput(
            plan_body="plan body",
            joined_work="work body",
            validate_body="validate body",
            verify_verdict_body='{"preliminary_verdict": "pass"}',
            report_html_path=Path("/tmp/run/report.html"),
            template_path=Path("/tmp/templates/report.html"),
        )
    )

    assert "plan body" in prompt
    assert "work body" in prompt
    assert "validate body" in prompt
    assert '"preliminary_verdict": "pass"' in prompt
    assert "/tmp/run/report.html" in prompt
    assert "/tmp/templates/report.html" in prompt


def test_build_report_initial_prompt_preserves_report_constraints() -> None:
    prompt = build_report_initial_prompt(
        ReportPromptInput(
            plan_body="",
            joined_work="",
            validate_body="",
            verify_verdict_body="{}",
            report_html_path=Path("report.html"),
            template_path=Path("template.html"),
        )
    )

    assert "{{title}}" in prompt
    assert "{{summary}}" in prompt
    assert "{{phase_sections}}" in prompt
    assert "{{plan_md_link}}" in prompt
    assert "plan.md" in prompt
    assert "final decision" in prompt

