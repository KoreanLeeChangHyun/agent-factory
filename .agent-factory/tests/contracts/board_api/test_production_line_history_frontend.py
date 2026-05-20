"""T-513 P3 — REST history single source frontend static revolving (T-497 policy).

Warranty:
  - REST single calling production-line-workflow.js GET /api/v2/sessions/<id>/history
    Source history loader (fetchHistory) exposed
  - Call Pattern: fetch + cache no-store (REST + cache invalid)
  - SSE Ringbuckle Replay Unused (T-497 Crystal)

production endpoint direct call ban (board.md §0.1). This test is only static analysis.
"""

from __future__ import annotations

import re
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[3].parent
_PRODUCTION_LINE_WORKFLOW_JS = (
    _REPO_ROOT / ".agent-factory" / "board" / "web" / "js" / "workflow"
    / "production-line-workflow.js"
)


def _read_production_line_workflow_js() -> str:
    assert _PRODUCTION_LINE_WORKFLOW_JS.exists(), f"production-line-workflow.js not found: {_PRODUCTION_LINE_WORKFLOW_JS}"
    return _PRODUCTION_LINE_WORKFLOW_JS.read_text(encoding="utf-8")


def test_production_line_workflow_js_exposes_fetch_history() -> None:
    """production-line-workflow.js registers Board.productionLineWorkflow.fetchHistory."""
    src = _read_production_line_workflow_js()
    assert "function fetchHistory(" in src, (
        "fetchHistory function is not defined in production-line-workflow.js"
    )
    assert "fetchHistory: fetchHistory" in src, (
        "fetchHistory not registered on Board.productionLineWorkflow API surface"
    )


def test_production_line_workflow_js_calls_history_endpoint() -> None:
    """fetchHistory calls GET /api/v2/sessions/<id>/history."""
    src = _read_production_line_workflow_js()
    # URL construction pattern — /api/v2/sessions/" + encodeURIComponent(sessionId) + "/history
    pattern = re.compile(
        r'["\']/api/v2/sessions/["\']\s*\+\s*encodeURIComponent\(sessionId\)'
        r'\s*\+\s*["\']/history["\']'
    )
    assert pattern.search(src), (
        "fetchHistory does not call /api/v2/sessions/<id>/history endpoint"
    )


def test_production_line_workflow_js_uses_rest_not_sse_replay() -> None:
    """fetchHistory is fetch-based REST — no SSE ringbuffer replay keyword."""
    src = _read_production_line_workflow_js()
    # Using fetch + cache no-store pattern in fetchHistory body
    assert "_fetchJson" in src, "_fetchJson helper not used"
    # SSE replay keyword (history live SSE replay) is not introduced in production-line-workflow.js
    forbidden = ("ring_buffer", "ringBuffer", "sse_replay", "sseReplay")
    for token in forbidden:
        assert token not in src, (
            f"Introducing SSE ringbuffer/replay keywords in production-line-workflow.js — REST single-source violation: {token}"
        )


def test_production_line_workflow_js_history_doc_present() -> None:
    """Specify the history endpoint item in the production-line-workflow.js header document (consumption contract)."""
    src = _read_production_line_workflow_js()
    # Specify /api/v2/sessions/<id>/history in module docstring or jsdoc area
    assert "/api/v2/sessions/<id>/history" in src, (
        "Omission of history endpoint in production-line-workflow.js module header"
    )
