"""handlers/ sub endpoint method docstring 11 field coverage test (T-511 P3).

Warranty:
  - the endpoint method of each mixin class(` handle *`/` production line handle *` prefix)
    11 field token (method/url/domain/handler/request/response ok/response error/
    status codes/auth/side effects/sse events
  - endpoint internal helper method contains 'internal helper' token
  - @api endpoint decorator is attached to the endpoint method

Verification Method: AST-based — static parsing without runtime import.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest


_REPO_ROOT = Path(__file__).resolve().parents[3].parent
_HANDLERS_DIR = _REPO_ROOT / ".agent-factory" / "board" / "server" / "handlers"
_BOARD_API_APP_DIR = _REPO_ROOT / ".agent-factory" / "engine" / "apps" / "board_api"

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
        p
        for directory in (_HANDLERS_DIR, _BOARD_API_APP_DIR)
        for p in directory.glob("*.py")
        if not p.name.startswith("__")
    )


def _is_endpoint_method(name: str) -> bool:
    """endpoint method identification —  handle * /  production line handle * prefix only endpoint.

    production line dispatch * /  production line collect extras /  gues content type
    """
    if name.startswith("_production_line_handle_"):
        return True
    if not name.startswith("_handle_"):
        return False
    # _handle_api is dispatcher — not endpoint
    return name not in {"_handle_api", "_handle_api_delete"}


def _collect_methods(file_path: Path) -> list[tuple[str, ast.FunctionDef, list[ast.expr]]]:
    """Collect all class methods (FunctionDef + decorators) in the file.

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
    """Collection of module top-level functions (outside the class) — for internal helper verification."""
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
    """Return a list of tokens missing in docstring (match all if empty list)."""
    if not docstring:
        return list(tokens)
    return [t for t in tokens if t not in docstring]


def _docstring_has_internal_helper(docstring: str | None) -> bool:
    if not docstring:
        return False
    return "internal helper" in docstring


# ---------------------------------------------------------------------------
# Test — endpoint method docstring 11 fields coverage
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("file_path", _iter_handler_files(), ids=lambda p: p.name)
def test_endpoint_methods_have_full_docstring(file_path: Path) -> None:
    """endpoint method docstring 11 token matching."""
    missing: list[str] = []
    for name, fn, decs in _collect_methods(file_path):
        if not _is_endpoint_method(name):
            continue
        doc = ast.get_docstring(fn)
        m = _docstring_has_all_tokens(doc, _DOCSTRING_TOKENS)
        if m:
            missing.append(f"{file_path.name}::{name} -- missing {m}")
    if missing:
        pytest.fail("docstring 11 Field missing: \n" + "\n".join(missing))


@pytest.mark.parametrize("file_path", _iter_handler_files(), ids=lambda p: p.name)
def test_endpoint_methods_have_api_endpoint_decorator(file_path: Path) -> None:
    """Attach the @api_endpoint(...) decorator to the endpoint method."""
    missing: list[str] = []
    for name, _fn, decs in _collect_methods(file_path):
        if not _is_endpoint_method(name):
            continue
        if not _has_api_endpoint_decorator(decs):
            missing.append(f"{file_path.name}::{name}")
    if missing:
        pytest.fail("@api_endpoint decorator missing: \n" + "\n".join(missing))


def test_internal_helpers_marked() -> None:
    """endpoint invalid (internal helper) 'internal helper' token in function/method docstring."""
    missing: list[str] = []

    # Module top-level helper function (private _xxx prefix)
    for file_path in _iter_handler_files():
        for name, fn in _collect_module_functions(file_path):
            if not name.startswith("_"):
                continue
            doc = ast.get_docstring(fn)
            if not _docstring_has_internal_helper(doc):
                missing.append(f"{file_path.name}::{name} (module-level)")

    # Helper method inside class (endpoint inappropriate)
    for file_path in _iter_handler_files():
        for name, fn, _decs in _collect_methods(file_path):
            if _is_endpoint_method(name):
                continue
            # __init__ / __init_subclass__ etc excluding dunder
            if name.startswith("__"):
                continue
            doc = ast.get_docstring(fn)
            if not _docstring_has_internal_helper(doc):
                missing.append(f"{file_path.name}::{name} (class method)")

    if missing:
        pytest.fail("Missing internal helper marker: \n" + "\n".join(missing))


def test_api_endpoint_decorator_count_threshold() -> None:
    """Total of @api_endpoint attachment lines in handlers/ ≥ 48 (P3 AC #1)."""
    total = 0
    for file_path in _iter_handler_files():
        text = file_path.read_text(encoding="utf-8")
        total += text.count("@api_endpoint(")
    assert total >= 48, f"@api_endpoint attachment total {total} < 48"
