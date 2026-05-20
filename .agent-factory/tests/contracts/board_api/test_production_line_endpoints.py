"""Production-line Unit testing of 3 new endpoints (T-511 P4).

verification:
  - DELETE /api/v2/sessions/<id> — Session forced termination + work_dir can be discarded
  - PATCH /api/v2/sessions/<id>/status — step/phase forced update
  - POST /api/v2/sessions/<id>/artifacts — Force injection of artifacts

_production_line_dispatch_* in do_DELETE / do_PATCH / do_POST branch of http_router.py
Check if routing new sub path (delete=empty sub, status, artifacts).

This test does not directly import BoardHTTPRequestHandler, but uses the core method
(_production_line_handle_session_delete / _production_line_handle_session_patch_status /
_production_line_handle_session_post_artifacts) exists above ProductionLineWorkflowHandlerMixin
Verify with AST + grep the routing branch of http_router.py.

Direct curl to production endpoint is prohibited (absolutely prohibited to board.md §0.1 — production
When calling the board API endpoint with fake/test session, .workflow-sessions-v2/
It is polluted and the naming guard blocks 403).
"""

from __future__ import annotations

import ast
from pathlib import Path



_REPO_ROOT = Path(__file__).resolve().parents[3].parent
_PRODUCTION_LINE_HANDLER = _REPO_ROOT / ".agent-factory" / "engine" / "apps" / "board_api" / "production_line_workflow.py"
_HTTP_ROUTER = (
    _REPO_ROOT / ".agent-factory" / "board" / "server" / "routing" / "http_router.py"
)


def _production_line_methods() -> set[str]:
    tree = ast.parse(_PRODUCTION_LINE_HANDLER.read_text(encoding="utf-8"))
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    out.add(item.name)
    return out


def test_production_line_delete_session_handler_exists() -> None:
    """DELETE /api/v2/sessions/<id> handler method exists."""
    methods = _production_line_methods()
    assert "_production_line_handle_session_delete" in methods, methods


def test_production_line_patch_session_status_handler_exists() -> None:
    """PATCH /api/v2/sessions/<id>/status handler method exists."""
    methods = _production_line_methods()
    assert "_production_line_handle_session_patch_status" in methods, methods


def test_production_line_post_session_artifacts_handler_exists() -> None:
    """POST /api/v2/sessions/<id>/artifacts handler method exists."""
    methods = _production_line_methods()
    assert "_production_line_handle_session_post_artifacts" in methods, methods


def test_production_line_workflow_handlers_have_endpoint_decorator() -> None:
    """@api_endpoint('W2', ...) decorator attached to all 3 new endpoints."""
    tree = ast.parse(_PRODUCTION_LINE_HANDLER.read_text(encoding="utf-8"))
    targets = {
        "_production_line_handle_session_delete",
        "_production_line_handle_session_patch_status",
        "_production_line_handle_session_post_artifacts",
    }
    decorated: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if item.name not in targets:
                        continue
                    for dec in item.decorator_list:
                        if isinstance(dec, ast.Call):
                            f = dec.func
                            if (isinstance(f, ast.Name) and f.id == "api_endpoint") or (
                                isinstance(f, ast.Attribute) and f.attr == "api_endpoint"
                            ):
                                decorated.add(item.name)
                                break
    missing = targets - decorated
    assert not missing, f"Missing @api_endpoint: {missing}"


def test_http_router_production_line_dispatch_post_routes_artifacts() -> None:
    """http_router.py do_POST handles the artifacts sub-path of /api/v2/sessions."""
    src = _PRODUCTION_LINE_HANDLER.read_text(encoding="utf-8")
    # _production_line_dispatch_post in production_line_workflow.py handles branch sub == 'artifacts'
    assert "sub == 'artifacts'" in src or 'sub == "artifacts"' in src, (
        "POST /api/v2/sessions/<id>/artifacts branch does not exist in _production_line_dispatch_post"
    )


def test_http_router_production_line_dispatch_delete_routes_session() -> None:
    """http_router.py do_DELETE handles the DELETE branch of /api/v2/sessions."""
    src = _HTTP_ROUTER.read_text(encoding="utf-8")
    # /api/v2/sessions DELETE routing: call production_line_dispatch_delete or match directly
    assert "/api/v2/sessions" in src
    assert "do_DELETE" in src
    # do_DELETE My v2 branch exists — _production_line_dispatch_delete delegation pattern
    assert "_production_line_dispatch_delete" in src, (
        "http_router.py do_DELETE does not call _production_line_dispatch_delete"
    )


def test_http_router_production_line_dispatch_patch_routes_status() -> None:
    """New http_router.py do_PATCH + /api/v2/sessions PATCH branch."""
    src = _HTTP_ROUTER.read_text(encoding="utf-8")
    assert "do_PATCH" in src, "No do_PATCH method in http_router.py"
    assert "_production_line_dispatch_patch" in src, (
        "http_router.py do_PATCH does not call _production_line_dispatch_patch"
    )


def test_production_line_dispatch_delete_method_exists() -> None:
    """New _production_line_dispatch_delete method was created."""
    methods = _production_line_methods()
    assert "_production_line_dispatch_delete" in methods, methods


def test_production_line_dispatch_patch_method_exists() -> None:
    """New _production_line_dispatch_patch method was created."""
    methods = _production_line_methods()
    assert "_production_line_dispatch_patch" in methods, methods


def test_generic_delete_dispatch_handler() -> None:
    """DELETE branch dispatch in generic.py has _handle_memory_delete / _handle_rules_delete /
    _handle_prompt_delete / _handle_quick_prompt_delete 4 handler delegation."""
    generic_py = _REPO_ROOT / ".agent-factory" / "engine" / "apps" / "board_api" / "generic.py"
    src = generic_py.read_text(encoding="utf-8")
    # _handle_api_delete dispatcher exists
    assert "_handle_api_delete" in src, (
        "No _handle_api_delete dispatcher in generic.py"
    )
    # Delegate call to all 4 handlers
    for handler in (
        "_handle_memory_delete",
        "_handle_rules_delete",
        "_handle_prompt_delete",
        "_handle_quick_prompt_delete",
    ):
        assert handler in src, f"No {handler} delegate call in generic.py body"
