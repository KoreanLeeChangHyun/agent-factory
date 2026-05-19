"""T-513 P1 — GET /api/v2/sessions/<id>/history endpoint 단위 회귀.

검증:
  - V2WorkflowSSEChannel.persist_path public property 정합
  - _v2_handle_session_history handler 존재 + @api_endpoint("W2", "history") decorator
  - _v2_dispatch_get sub == 'history' 분기 라우팅
  - end-to-end: tempfile NDJSON read 결과가 응답 events 와 1:1 (_meta 라인 건너뜀)

production endpoint 직접 curl 금지 (board.md §0.1 — production session 오염
+ naming guard 403 차단). 본 테스트는 tempfile + V2WorkflowSessionRegistry
직접 호출만 사용한다.
"""

from __future__ import annotations

import ast
import json
import tempfile
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[4]
_V2_HANDLER = _REPO_ROOT / ".claude-organic" / "board" / "server" / "handlers" / "v2_workflow.py"


def _v2_methods() -> set[str]:
    tree = ast.parse(_V2_HANDLER.read_text(encoding="utf-8"))
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    out.add(item.name)
    return out


def test_v2_sse_channel_persist_path_property() -> None:
    """V2WorkflowSSEChannel.persist_path public property — history handler 진입점."""
    from board.server.v2_sse_channel import V2WorkflowSSEChannel
    ch = V2WorkflowSSEChannel(session_id='wf-T-513-unit', persist_path='/tmp/v2-unit.jsonl')
    assert ch.persist_path == '/tmp/v2-unit.jsonl'
    ch_none = V2WorkflowSSEChannel(session_id='wf-T-513-unit-noper')
    assert ch_none.persist_path is None


def test_v2_history_handler_method_exists() -> None:
    """GET /api/v2/sessions/<id>/history handler 메서드 존재."""
    methods = _v2_methods()
    assert "_v2_handle_session_history" in methods, methods


def test_v2_history_handler_has_endpoint_decorator() -> None:
    """history handler 가 @api_endpoint('W2', 'history') decorator 부착."""
    tree = ast.parse(_V2_HANDLER.read_text(encoding="utf-8"))
    found = False
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if item.name != "_v2_handle_session_history":
                        continue
                    for dec in item.decorator_list:
                        if isinstance(dec, ast.Call):
                            f = dec.func
                            is_api_endpoint = (
                                (isinstance(f, ast.Name) and f.id == "api_endpoint")
                                or (isinstance(f, ast.Attribute) and f.attr == "api_endpoint")
                            )
                            if is_api_endpoint:
                                found = True
    assert found, "@api_endpoint decorator 누락"


def test_v2_dispatch_get_routes_history() -> None:
    """_v2_dispatch_get 가 sub == 'history' 분기를 처리한다."""
    src = _V2_HANDLER.read_text(encoding="utf-8")
    assert "sub == 'history'" in src or 'sub == "history"' in src, (
        "GET /api/v2/sessions/<id>/history 분기가 _v2_dispatch_get 에 없음"
    )


def test_v2_history_ndjson_read_end_to_end() -> None:
    """tempfile NDJSON 생성 → registry 등록 → broadcast 3건 → history 가 events 3건 반환."""
    from board.server.v2_workflow_session import V2WorkflowSessionRegistry

    with tempfile.TemporaryDirectory() as td:
        reg = V2WorkflowSessionRegistry(persist_dir=td)
        # production-pattern session_id (fake-pattern guard 통과)
        sid = 'wf-T-513-abc12345-6789-4abc-9def-0123456789ab'
        session = reg.create(
            session_id=sid,
            ticket_id='T-513',
            command='implement',
            work_dir='/tmp/wd-history-test',
        )
        # 이벤트 broadcast (클라이언트 0건 — persist 만 확인)
        session.channel.broadcast('workflow_step', {'session_id': sid, 'step': 'INIT'})
        session.channel.broadcast('workflow_step', {'session_id': sid, 'step': 'PLAN'})
        session.channel.broadcast('workflow_finish', {'session_id': sid, 'outcome': 'ok'})

        # history handler 본체 로직 simulation — persist 파일 read 결과 events
        persist_path = session.channel.persist_path
        assert persist_path is not None
        events: list = []
        with open(persist_path, encoding='utf-8') as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                if isinstance(rec, dict) and '_meta' in rec:
                    continue
                events.append(rec)

        assert len(events) == 3, events
        assert events[0]['event'] == 'workflow_step'
        assert events[0]['payload']['step'] == 'INIT'
        assert events[1]['payload']['step'] == 'PLAN'
        assert events[2]['event'] == 'workflow_finish'
        assert events[2]['payload']['outcome'] == 'ok'
