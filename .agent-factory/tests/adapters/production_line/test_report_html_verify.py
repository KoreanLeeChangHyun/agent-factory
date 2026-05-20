"""test_report_html_verify.py — T-504 P3 (TDD Red→Green→Refactor).

Target:
- Presence of core reporting `report.html` + required token (terracotta / prefers-reduced-motion / placeholder)
- Behavior of `engine.apps.production_line._verify.verify_report_html` (R-EXIST-1 target change after T-504 cutover)
- Template body can be loaded with `engine.apps.production_line._common.load_template("report.html")`
"""

from __future__ import annotations

from pathlib import Path

import pytest

from engine.core.reporting.templates import load_report_template, report_template_path
from engine.apps.production_line._common import load_template
from engine.apps.production_line._verify import verify_report_html


def test_report_html_template_exists() -> None:
    """`templates/report.html` file exists + 0 bytes exceeded."""
    path = report_template_path()
    assert path.exists(), f"template missing: {path}"
    assert path.stat().st_size > 0


def test_report_html_template_has_terracotta_token() -> None:
    """board.md §6 Canon — terracotta `#D97757` 1+ appearances."""
    text = load_report_template()
    assert "#D97757" in text, "terracotta color token missing"


def test_report_html_template_has_prefers_reduced_motion() -> None:
    """Accessibility Canon — `prefers-reduced-motion` guard 1+ appears."""
    text = load_report_template()
    assert "prefers-reduced-motion" in text, (
        "prefers-reduced-motion accessibility guard missing"
    )


def test_report_html_template_has_placeholders() -> None:
    """4 types of required placeholders ({{title}} / {{summary}} / {{phase_sections}} /
    {{plan_md_link}}) all exist."""
    text = load_report_template()
    for token in ("{{title}}", "{{summary}}", "{{phase_sections}}", "{{plan_md_link}}"):
        assert token in text, f"placeholder {token!r} missing"


def test_report_html_template_has_doctype_html() -> None:
    text = load_report_template()
    assert "<!DOCTYPE html>" in text or "<!doctype html>" in text.lower()
    assert "<html" in text and "</html>" in text


def test_report_html_template_plan_md_link() -> None:
    """plan/plan.md reference token — Contains `<a href=` or plain text 'plan.md'."""
    text = load_report_template()
    assert "plan.md" in text


def test_production_line_load_template_keeps_report_html_compatibility() -> None:
    assert load_template("report.html") == load_report_template()


@pytest.fixture
def sample_report_html(tmp_path: Path) -> tuple[Path, Path]:
    """report.html + plan.md fixture — verify_report_html passing scenario."""
    plan = tmp_path / "plan" / "plan.md"
    plan.parent.mkdir(parents=True)
    plan.write_text("body" * 20, encoding="utf-8")
    report = tmp_path / "report.html"
    report.write_text(
        "<!doctype html><html><body><p>refers to plan.md output</p></body></html>"
        + "x" * 100,
        encoding="utf-8",
    )
    return report, plan


def test_verify_report_html_pass(sample_report_html: tuple[Path, Path]) -> None:
    report, plan = sample_report_html
    result = verify_report_html(report, plan)
    assert result.ok
    assert result.missing == []


def test_verify_report_html_missing_file(tmp_path: Path) -> None:
    result = verify_report_html(
        tmp_path / "nope.html",
        tmp_path / "plan" / "plan.md",
    )
    assert not result.ok
    assert any("file not found" in m for m in result.missing)


def test_verify_report_html_too_small(tmp_path: Path) -> None:
    plan = tmp_path / "plan" / "plan.md"
    plan.parent.mkdir(parents=True)
    plan.write_text("dummy", encoding="utf-8")
    report = tmp_path / "report.html"
    report.write_text("<html></html>", encoding="utf-8")  # 13 bytes < 50
    result = verify_report_html(report, plan)
    assert not result.ok
    assert any("too small" in m for m in result.missing)


def test_verify_report_html_missing_plan_token(tmp_path: Path) -> None:
    plan = tmp_path / "plan" / "plan.md"
    plan.parent.mkdir(parents=True)
    plan.write_text("dummy", encoding="utf-8")
    report = tmp_path / "report.html"
    report.write_text("<html>" + "x" * 100 + "</html>", encoding="utf-8")
    result = verify_report_html(report, plan)
    assert not result.ok
    assert any("plan.md" in m for m in result.missing)
