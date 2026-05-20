"""Report template ownership."""

from __future__ import annotations

from pathlib import Path


REPORT_TEMPLATE_NAME = "report.html"
REPORT_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"


def report_template_path() -> Path:
    return REPORT_TEMPLATE_DIR / REPORT_TEMPLATE_NAME


def load_report_template() -> str:
    return report_template_path().read_text(encoding="utf-8")

