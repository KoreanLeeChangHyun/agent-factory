"""T-513 P3 — REST history 단일 출처 frontend 정합 회귀 (T-497 정책).

검증:
  - v2-workflow.js 가 GET /api/v2/sessions/<id>/history 를 호출하는 REST 단일
    출처 history loader (fetchHistory) 를 노출
  - 호출 패턴: fetch + cache no-store (REST + 캐시 무효)
  - SSE 링버퍼 replay 사용 안 함 (T-497 결정점 정합)

production endpoint 직접 호출 금지 (board.md §0.1). 본 테스트는 정적 분석만.
"""

from __future__ import annotations

import re
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[4]
_V2_WORKFLOW_JS = (
    _REPO_ROOT / ".claude-organic" / "board" / "static" / "js" / "workflow"
    / "v2-workflow.js"
)


def _read_v2_workflow_js() -> str:
    assert _V2_WORKFLOW_JS.exists(), f"v2-workflow.js not found: {_V2_WORKFLOW_JS}"
    return _V2_WORKFLOW_JS.read_text(encoding="utf-8")


def test_v2_workflow_js_exposes_fetch_history() -> None:
    """v2-workflow.js 가 Board.v2Workflow.fetchHistory 를 등록한다."""
    src = _read_v2_workflow_js()
    assert "function fetchHistory(" in src, (
        "fetchHistory 함수가 v2-workflow.js 에 정의되지 않음"
    )
    assert "fetchHistory: fetchHistory" in src, (
        "Board.v2Workflow API 표면에 fetchHistory 가 등록되지 않음"
    )


def test_v2_workflow_js_calls_history_endpoint() -> None:
    """fetchHistory 가 GET /api/v2/sessions/<id>/history 를 호출한다."""
    src = _read_v2_workflow_js()
    # URL 구성 패턴 — /api/v2/sessions/" + encodeURIComponent(sessionId) + "/history
    pattern = re.compile(
        r'["\']/api/v2/sessions/["\']\s*\+\s*encodeURIComponent\(sessionId\)'
        r'\s*\+\s*["\']/history["\']'
    )
    assert pattern.search(src), (
        "fetchHistory 가 /api/v2/sessions/<id>/history endpoint 를 호출하지 않음"
    )


def test_v2_workflow_js_uses_rest_not_sse_replay() -> None:
    """fetchHistory 가 fetch 기반 REST — SSE 링버퍼 replay 키워드 없음."""
    src = _read_v2_workflow_js()
    # fetchHistory 본체에서 fetch + cache no-store 패턴 사용
    assert "_fetchJson" in src, "_fetchJson 헬퍼 미사용"
    # SSE replay 키워드 (history 라이브 SSE 재전송) 가 v2-workflow.js 에 도입되지 않음
    forbidden = ("ring_buffer", "ringBuffer", "sse_replay", "sseReplay")
    for token in forbidden:
        assert token not in src, (
            f"v2-workflow.js 에 SSE 링버퍼/replay 키워드 도입 — REST 단일 출처 위반: {token}"
        )


def test_v2_workflow_js_history_doc_present() -> None:
    """v2-workflow.js 헤더 문서에 history endpoint 항목 명시 (소비 계약)."""
    src = _read_v2_workflow_js()
    # 모듈 docstring 또는 jsdoc 영역에 /api/v2/sessions/<id>/history 명시
    assert "/api/v2/sessions/<id>/history" in src, (
        "v2-workflow.js 모듈 헤더에 history endpoint 명시 누락"
    )
