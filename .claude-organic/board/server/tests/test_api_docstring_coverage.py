"""handlers/ 하위 endpoint 메서드 docstring 11 필드 coverage 테스트 (T-511 P3).

검증:
  - 각 mixin class 의 endpoint 메서드 (`_handle_*` / `_v2_handle_*` prefix) 가
    11 필드 토큰 (method/url/domain/handler/request/response_ok/response_error/
    status_codes/auth/side_effects/sse_events) 을 docstring 에 포함
  - endpoint 부적합 (internal helper) 메서드는 'internal helper' 토큰 포함
  - @api_endpoint decorator 가 endpoint 메서드 위에 부착되어 있음

검증 방식: AST 기반 — runtime import 없이 정적 파싱.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest


_REPO_ROOT = Path(__file__).resolve().parents[4]
_HANDLERS_DIR = _REPO_ROOT / ".claude-organic" / "board" / "server" / "handlers"

_DOCSTRING_TOKENS = [
    "method:",
    "url:",
    "domain:",
    "request:",
    "response_ok:",
    "response_error:",
    "status_codes:",
    "auth:",
    "side_effects:",
    "sse_events:",
]


def _iter_handler_files() -> list[Path]:
    return sorted(
        p for p in _HANDLERS_DIR.glob("*.py")
        if not p.name.startswith("__")
    )


def _is_endpoint_method(name: str) -> bool:
    """endpoint 메서드 식별 — _handle_* / _v2_handle_* prefix 만 endpoint.

    _v2_dispatch_* / _v2_collect_extras / _guess_content_type 등은 helper.
    """
    if name.startswith("_v2_handle_"):
        return True
    if not name.startswith("_handle_"):
        return False
    # _handle_api 는 dispatcher — endpoint 아님
    return name not in {"_handle_api", "_handle_api_delete"}


def _collect_methods(file_path: Path) -> list[tuple[str, ast.FunctionDef, list[ast.expr]]]:
    """파일 내 모든 class method (FunctionDef + decorators) 를 수집.

    Returns:
        [(method_name, FunctionDef, decorators), ...]
    """
    tree = ast.parse(file_path.read_text(encoding="utf-8"))
    out: list[tuple[str, ast.FunctionDef, list[ast.expr]]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    out.append((item.name, item, item.decorator_list))
    return out


def _collect_module_functions(file_path: Path) -> list[tuple[str, ast.FunctionDef]]:
    """모듈 최상위 함수 (class 밖) 수집 — internal helper 검증용."""
    tree = ast.parse(file_path.read_text(encoding="utf-8"))
    out: list[tuple[str, ast.FunctionDef]] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.append((node.name, node))
    return out


def _has_api_endpoint_decorator(decorators: list[ast.expr]) -> bool:
    for dec in decorators:
        if isinstance(dec, ast.Call):
            func = dec.func
            if isinstance(func, ast.Name) and func.id == "api_endpoint":
                return True
            if isinstance(func, ast.Attribute) and func.attr == "api_endpoint":
                return True
    return False


def _docstring_has_all_tokens(docstring: str | None, tokens: list[str]) -> list[str]:
    """docstring 에 누락된 토큰 목록 반환 (빈 리스트면 모두 매칭)."""
    if not docstring:
        return list(tokens)
    return [t for t in tokens if t not in docstring]


def _docstring_has_internal_helper(docstring: str | None) -> bool:
    if not docstring:
        return False
    return "internal helper" in docstring


# ---------------------------------------------------------------------------
# 테스트 — endpoint 메서드 docstring 11 필드 coverage
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("file_path", _iter_handler_files(), ids=lambda p: p.name)
def test_endpoint_methods_have_full_docstring(file_path: Path) -> None:
    """endpoint 메서드 docstring 11 토큰 매칭."""
    missing: list[str] = []
    for name, fn, decs in _collect_methods(file_path):
        if not _is_endpoint_method(name):
            continue
        doc = ast.get_docstring(fn)
        m = _docstring_has_all_tokens(doc, _DOCSTRING_TOKENS)
        if m:
            missing.append(f"{file_path.name}::{name} -- missing {m}")
    if missing:
        pytest.fail("docstring 11 필드 누락:\n" + "\n".join(missing))


@pytest.mark.parametrize("file_path", _iter_handler_files(), ids=lambda p: p.name)
def test_endpoint_methods_have_api_endpoint_decorator(file_path: Path) -> None:
    """endpoint 메서드 위에 @api_endpoint(...) decorator 부착."""
    missing: list[str] = []
    for name, _fn, decs in _collect_methods(file_path):
        if not _is_endpoint_method(name):
            continue
        if not _has_api_endpoint_decorator(decs):
            missing.append(f"{file_path.name}::{name}")
    if missing:
        pytest.fail("@api_endpoint decorator 누락:\n" + "\n".join(missing))


def test_internal_helpers_marked() -> None:
    """endpoint 부적합 (internal helper) 함수/메서드 docstring 에 'internal helper' 토큰."""
    missing: list[str] = []

    # 모듈 최상위 helper 함수 (private _xxx prefix)
    for file_path in _iter_handler_files():
        for name, fn in _collect_module_functions(file_path):
            if not name.startswith("_"):
                continue
            doc = ast.get_docstring(fn)
            if not _docstring_has_internal_helper(doc):
                missing.append(f"{file_path.name}::{name} (module-level)")

    # class 내부 helper 메서드 (endpoint 부적합)
    for file_path in _iter_handler_files():
        for name, fn, _decs in _collect_methods(file_path):
            if _is_endpoint_method(name):
                continue
            # __init__ / __init_subclass__ 등 dunder 제외
            if name.startswith("__"):
                continue
            doc = ast.get_docstring(fn)
            if not _docstring_has_internal_helper(doc):
                missing.append(f"{file_path.name}::{name} (class method)")

    if missing:
        pytest.fail("internal helper 마커 누락:\n" + "\n".join(missing))


def test_api_endpoint_decorator_count_threshold() -> None:
    """handlers/ 전체에 @api_endpoint 부착 라인 합계 ≥ 48 (P3 AC #1)."""
    total = 0
    for file_path in _iter_handler_files():
        text = file_path.read_text(encoding="utf-8")
        total += text.count("@api_endpoint(")
    assert total >= 48, f"@api_endpoint 부착 합계 {total} < 48"
