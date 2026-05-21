"""WR-513 P1 — GET /api/v2/sessions/<id>/history endpoint unit regression.

Warranty:
  - ProductionLineSSEChannel.persist path public property
  <% if (imgObj.width >= imgObj.height) { %> <% if (image rate > 5) { %>
  -  production line dispatch get sub == 'history' routing
  - end-to-end: tempfile NDJSON read results in response events and 1:1 ( meta-line skip)

production endpoint direct curl ban (board.md §0.1 — production session contamination
+ naming guard 403 blocking). Production Line
Use only direct calls.
"""

from __future__ import annotations

import ast
import json
import tempfile
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[3].parent
_PRODUCTION_LINE_HANDLER = _REPO_ROOT / ".agent-factory" / "engine" / "apps" / "board_api" / "production_line_workflow.py"


def _production_line_methods() -> set[str]:
    tree = ast.parse(_PRODUCTION_LINE_HANDLER.read_text(encoding="utf-8"))
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    out.add(item.name)
    return out


def test_production_line_sse_channel_persist_path_property() -> None:
    """ProductionLineSSEChannel.persist_path public property — history handler entry point."""
    from board.server.channels.production_line_sse_channel import ProductionLineSSEChannel
    ch = ProductionLineSSEChannel(session_id='wf-WR-513-unit', persist_path='/tmp/production-line-unit.jsonl')
    assert ch.persist_path == '/tmp/production-line-unit.jsonl'
    ch_none = ProductionLineSSEChannel(session_id='wf-WR-513-unit-noper')
    assert ch_none.persist_path is None


def test_production_line_history_handler_method_exists() -> None:
    """GET /api/v2/sessions/<id>/history handler method exists."""
    methods = _production_line_methods()
    assert "_production_line_handle_session_history" in methods, methods


def test_production_line_history_handler_has_endpoint_decorator() -> None:
    """The history handler attaches the @api_endpoint('W2', 'history') decorator."""
    tree = ast.parse(_PRODUCTION_LINE_HANDLER.read_text(encoding="utf-8"))
    found = False
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if item.name != "_production_line_handle_session_history":
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
    assert found, "Missing @api_endpoint decorator"


def test_production_line_dispatch_get_routes_history() -> None:
    """_production_line_dispatch_get handles the sub == 'history' branch."""
    src = _PRODUCTION_LINE_HANDLER.read_text(encoding="utf-8")
    assert "sub == 'history'" in src or 'sub == "history"' in src, (
        "GET /api/v2/sessions/<id>/history branch does not exist in _production_line_dispatch_get"
    )


def test_production_line_history_ndjson_read_end_to_end() -> None:
    """Create tempfile NDJSON → Register in registry → 3 broadcasts → History returns 3 events."""
    from board.server.sessions.production_line_session import ProductionLineSessionRegistry

    with tempfile.TemporaryDirectory() as td:
        reg = ProductionLineSessionRegistry(persist_dir=td)
        # production-pattern session_id (passes fake-pattern guard)
        sid = 'wf-WR-513-abc12345-6789-4abc-9def-0123456789ab'
        session = reg.create(
            session_id=sid,
            work_request='WR-513',
            command='implement',
            work_dir='/tmp/wd-history-test',
        )
        # Event broadcast (0 clients — only confirms persist)
        session.channel.broadcast('workflow_step', {'session_id': sid, 'step': 'INIT'})
        session.channel.broadcast('workflow_step', {'session_id': sid, 'step': 'PLAN'})
        session.channel.broadcast('workflow_finish', {'session_id': sid, 'outcome': 'ok'})

        # History handler main body logic simulation — persist file read result events
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


def test_production_line_session_default_persist_path_is_run_local() -> None:
    """No global .workflow-sessions-v2 dir is needed for production-line history."""
    from board.server.sessions.production_line_session import ProductionLineSessionRegistry

    with tempfile.TemporaryDirectory() as td:
        reg = ProductionLineSessionRegistry()
        sid = 'wf-WR-517-abc12345-6789-4abc-9def-0123456789ab'
        session = reg.create(
            session_id=sid,
            work_request='WR-517',
            command='implement',
            work_dir=td,
        )

        assert session.channel.persist_path == str(
            Path(td) / 'workflow-events.jsonl'
        )
        assert Path(session.channel.persist_path).exists()


def test_board_startup_does_not_create_production_line_sessions_root() -> None:
    """The board app no longer initializes the old .workflow-sessions-v2 cache."""
    app_src = (
        Path(__file__).resolve().parents[3].parent
            / ".agent-factory"
            / "board"
            / "server"
            / "runtime"
            / "app.py"
    ).read_text(encoding="utf-8")

    assert "os.makedirs(v2_sessions_dir" not in app_src
    assert ".workflow-sessions-v2" not in app_src


def test_board_startup_does_not_create_v1_workflow_sessions_root() -> None:
    """The board app no longer initializes the old V1 workflow session cache."""
    app_src = (
        Path(__file__).resolve().parents[3].parent
            / ".agent-factory"
            / "board"
            / "server"
            / "runtime"
            / "app.py"
    ).read_text(encoding="utf-8")

    assert "workflow_registry.load_from_disk()" not in app_src
    assert ".workflow-sessions" not in app_src
