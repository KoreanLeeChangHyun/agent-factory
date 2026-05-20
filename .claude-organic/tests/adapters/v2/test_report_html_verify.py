"""test_report_html_verify.py — T-504 P3 (TDD Red→Green→Refactor).

대상:
- `engine.v2.templates/report.html` 의 존재 + 필수 토큰 (terracotta / prefers-reduced-motion / placeholder)
- `engine.v2._verify.verify_report_html` 의 동작 (T-504 cutover 후 R-EXIST-1 대상 변경)
- `engine.v2._common.load_template("report.html")` 로 template 본문 로딩 가능
"""

from __future__ import annotations

from pathlib import Path

import pytest

from engine.v2._common import TEMPLATES_DIR, load_template
from engine.v2._verify import verify_report_html


def test_report_html_template_exists() -> None:
    """`templates/report.html` 파일 실재 + 0 byte 초과."""
    path = TEMPLATES_DIR / "report.html"
    assert path.exists(), f"template missing: {path}"
    assert path.stat().st_size > 0


def test_report_html_template_has_terracotta_token() -> None:
    """board.md §6 캐논 — terracotta `#D97757` 1+ 출현."""
    text = load_template("report.html")
    assert "#D97757" in text, "terracotta color token missing"


def test_report_html_template_has_prefers_reduced_motion() -> None:
    """접근성 캐논 — `prefers-reduced-motion` 가드 1+ 출현."""
    text = load_template("report.html")
    assert "prefers-reduced-motion" in text, (
        "prefers-reduced-motion accessibility guard missing"
    )


def test_report_html_template_has_placeholders() -> None:
    """필수 placeholder 4종 ({{title}} / {{summary}} / {{phase_sections}} /
    {{plan_md_link}}) 모두 존재."""
    text = load_template("report.html")
    for token in ("{{title}}", "{{summary}}", "{{phase_sections}}", "{{plan_md_link}}"):
        assert token in text, f"placeholder {token!r} missing"


def test_report_html_template_has_doctype_html() -> None:
    text = load_template("report.html")
    assert "<!DOCTYPE html>" in text or "<!doctype html>" in text.lower()
    assert "<html" in text and "</html>" in text


def test_report_html_template_plan_md_link() -> None:
    """plan/plan.md 참조 토큰 — `<a href=` 또는 plain text 'plan.md' 포함."""
    text = load_template("report.html")
    assert "plan.md" in text


@pytest.fixture
def sample_report_html(tmp_path: Path) -> tuple[Path, Path]:
    """report.html + plan.md fixture — verify_report_html 통과 시나리오."""
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
