"""v2 신규 endpoint 3건 단위 테스트 (T-511 P4).

검증:
  - DELETE /api/v2/sessions/<id> — 세션 강제 종료 + work_dir 폐기 가능
  - PATCH  /api/v2/sessions/<id>/status — step/phase 강제 갱신
  - POST   /api/v2/sessions/<id>/artifacts — 산출물 강제 주입

http_router.py 의 do_DELETE / do_PATCH / do_POST 분기에서 _v2_dispatch_* 가
신규 sub 경로 (delete=빈 sub, status, artifacts) 를 라우팅하는지 확인.

본 테스트는 BoardHTTPRequestHandler 를 직접 import 하지 않고, 핵심 메서드
(_v2_handle_session_delete / _v2_handle_session_patch_status /
_v2_handle_session_post_artifacts) 가 V2WorkflowHandlerMixin 위에 존재하는지
AST 로 검증한다 + http_router.py 의 routing 분기 grep.

production endpoint 직접 curl 금지 (board.md 절대 금지 §0.1 — production
board API endpoint 에 fake/test session 으로 호출하면 .workflow-sessions-v2/
오염되며 naming guard 가 403 차단).
"""

from __future__ import annotations

import ast
from pathlib import Path



_REPO_ROOT = Path(__file__).resolve().parents[4]
_V2_HANDLER = _REPO_ROOT / ".claude-organic" / "board" / "server" / "handlers" / "v2_workflow.py"
_HTTP_ROUTER = _REPO_ROOT / ".claude-organic" / "board" / "server" / "http_router.py"


def _v2_methods() -> set[str]:
    tree = ast.parse(_V2_HANDLER.read_text(encoding="utf-8"))
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    out.add(item.name)
    return out


def test_v2_delete_session_handler_exists() -> None:
    """DELETE /api/v2/sessions/<id> handler 메서드 존재."""
    methods = _v2_methods()
    assert "_v2_handle_session_delete" in methods, methods


def test_v2_patch_session_status_handler_exists() -> None:
    """PATCH /api/v2/sessions/<id>/status handler 메서드 존재."""
    methods = _v2_methods()
    assert "_v2_handle_session_patch_status" in methods, methods


def test_v2_post_session_artifacts_handler_exists() -> None:
    """POST /api/v2/sessions/<id>/artifacts handler 메서드 존재."""
    methods = _v2_methods()
    assert "_v2_handle_session_post_artifacts" in methods, methods


def test_v2_workflow_handlers_have_endpoint_decorator() -> None:
    """신설 3 endpoint 모두 @api_endpoint('W2', ...) decorator 부착."""
    tree = ast.parse(_V2_HANDLER.read_text(encoding="utf-8"))
    targets = {
        "_v2_handle_session_delete",
        "_v2_handle_session_patch_status",
        "_v2_handle_session_post_artifacts",
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
    assert not missing, f"@api_endpoint 누락: {missing}"


def test_http_router_v2_dispatch_post_routes_artifacts() -> None:
    """http_router.py do_POST 가 /api/v2/sessions 의 artifacts sub-path 처리."""
    src = _V2_HANDLER.read_text(encoding="utf-8")
    # v2_workflow.py 내 _v2_dispatch_post 가 sub == 'artifacts' 분기 처리
    assert "sub == 'artifacts'" in src or 'sub == "artifacts"' in src, (
        "POST /api/v2/sessions/<id>/artifacts 분기가 _v2_dispatch_post 에 없음"
    )


def test_http_router_v2_dispatch_delete_routes_session() -> None:
    """http_router.py do_DELETE 가 /api/v2/sessions 의 DELETE 분기 처리."""
    src = _HTTP_ROUTER.read_text(encoding="utf-8")
    # /api/v2/sessions DELETE 라우팅: v2_dispatch_delete 호출 또는 직접 매칭
    assert "/api/v2/sessions" in src
    assert "do_DELETE" in src
    # do_DELETE 내 v2 분기 존재 — _v2_dispatch_delete 위임 패턴
    assert "_v2_dispatch_delete" in src, (
        "http_router.py do_DELETE 가 _v2_dispatch_delete 를 호출하지 않음"
    )


def test_http_router_v2_dispatch_patch_routes_status() -> None:
    """http_router.py do_PATCH 신설 + /api/v2/sessions PATCH 분기."""
    src = _HTTP_ROUTER.read_text(encoding="utf-8")
    assert "do_PATCH" in src, "http_router.py 에 do_PATCH 메서드 없음"
    assert "_v2_dispatch_patch" in src, (
        "http_router.py do_PATCH 가 _v2_dispatch_patch 를 호출하지 않음"
    )


def test_v2_dispatch_delete_method_exists() -> None:
    """_v2_dispatch_delete 메서드 신설."""
    methods = _v2_methods()
    assert "_v2_dispatch_delete" in methods, methods


def test_v2_dispatch_patch_method_exists() -> None:
    """_v2_dispatch_patch 메서드 신설."""
    methods = _v2_methods()
    assert "_v2_dispatch_patch" in methods, methods


def test_generic_delete_dispatch_handler() -> None:
    """generic.py 에 DELETE 분기 dispatch 가 _handle_memory_delete / _handle_rules_delete /
    _handle_prompt_delete / _handle_quick_prompt_delete 4 handler 위임."""
    generic_py = _REPO_ROOT / ".claude-organic" / "board" / "server" / "handlers" / "generic.py"
    src = generic_py.read_text(encoding="utf-8")
    # _handle_api_delete dispatcher 존재
    assert "_handle_api_delete" in src, (
        "generic.py 에 _handle_api_delete dispatcher 가 없음"
    )
    # 4 handler 모두 위임 호출
    for handler in (
        "_handle_memory_delete",
        "_handle_rules_delete",
        "_handle_prompt_delete",
        "_handle_quick_prompt_delete",
    ):
        assert handler in src, f"generic.py 본문에 {handler} 위임 호출 없음"
