"""Board workflow artifact contract tests."""

from __future__ import annotations

import json
from pathlib import Path

from board.board_data import WF_DETAIL_FILES, _workflow_detail


def test_workflow_detail_uses_report_html_as_report_artifact() -> None:
    report = next(item for item in WF_DETAIL_FILES if item["key"] == "report")
    assert report["file"] == "report.html"


def test_workflow_detail_exposes_report_html_file_map(tmp_path: Path) -> None:
    run_dir = tmp_path / ".agent-factory" / "runs" / "20260520-120000"
    run_dir.mkdir(parents=True)
    (run_dir / "status.json").write_text(
        json.dumps({"workflow_step": "REPORT", "created_at": "", "updated_at": ""}),
        encoding="utf-8",
    )
    (run_dir / ".context.json").write_text(
        json.dumps({"command": "implement", "ticketNumber": "T-001", "title": "Report"}),
        encoding="utf-8",
    )
    (run_dir / "report.html").write_text("<html>report</html>", encoding="utf-8")

    detail = _workflow_detail(str(tmp_path), ".agent-factory/runs/20260520-120000/")

    assert len(detail) == 1
    assert detail[0]["fileMap"]["report"] == {
        "exists": True,
        "url": ".agent-factory/runs/20260520-120000/report.html",
    }
