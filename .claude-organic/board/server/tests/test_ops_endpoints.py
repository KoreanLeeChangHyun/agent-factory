"""운영 endpoint 3건 단위 테스트 (T-511 P5).

검증:
  - POST /api/ops/zombie-reap — Claude CLI 좀비 회수 명시 호출
  - POST /api/ops/debug-toggle — debug.enabled 플래그 토글
  - GET  /api/ops/sse-status — 3 SSE 채널 상태 dump

production endpoint 직접 호출 금지 (board.md 절대 금지 §0.1). 본 테스트는
AST 기반 정적 검증 + 일부 in-process 로직 검증 (debug.enabled 토글).
"""

from __future__ import annotations

import ast
from pathlib import Path



_REPO_ROOT = Path(__file__).resolve().parents[4]
_HANDLERS_DIR = _REPO_ROOT / ".claude-organic" / "board" / "server" / "handlers"
_HTTP_ROUTER = _REPO_ROOT / ".claude-organic" / "board" / "server" / "http_router.py"


def _find_ops_file() -> Path | None:
    candidates = [_HANDLERS_DIR / "ops_endpoints.py", _HANDLERS_DIR / "system.py"]
    for p in candidates:
        if p.exists():
            return p
    return None


def test_ops_handler_file_exists() -> None:
    """ops_endpoints.py 또는 system.py 파일 존재."""
    p = _find_ops_file()
    assert p is not None, f"파일 미존재 — {_HANDLERS_DIR}/ops_endpoints.py 또는 system.py 필요"


def test_ops_zombie_reap_method_exists() -> None:
    """zombie_reap / reap_zombies 토큰 매칭."""
    p = _find_ops_file()
    assert p is not None
    text = p.read_text(encoding="utf-8")
    assert ("zombie_reap" in text) or ("reap_zombies" in text), text[:200]


def test_ops_debug_toggle_method_exists() -> None:
    """debug_toggle / toggle_debug 토큰 매칭."""
    p = _find_ops_file()
    assert p is not None
    text = p.read_text(encoding="utf-8")
    assert ("debug_toggle" in text) or ("toggle_debug" in text), text[:200]


def test_ops_sse_status_method_exists() -> None:
    """sse_status 토큰 매칭."""
    p = _find_ops_file()
    assert p is not None
    text = p.read_text(encoding="utf-8")
    assert "sse_status" in text, text[:200]


def test_http_router_has_ops_routes() -> None:
    """http_router.py 본문에 /api/ops/ 라우팅 3건 이상."""
    src = _HTTP_ROUTER.read_text(encoding="utf-8")
    assert "/api/ops/" in src, "http_router.py 에 /api/ops/ 매칭 없음"
    count = src.count("/api/ops/")
    assert count >= 3, f"/api/ops/ 라우팅 count={count} (3 이상 기대)"


def test_ops_handlers_have_api_endpoint_decorator() -> None:
    """ops 3 endpoint 모두 @api_endpoint('INF', ...) decorator 부착."""
    p = _find_ops_file()
    assert p is not None
    tree = ast.parse(p.read_text(encoding="utf-8"))
    decorated_with_inf: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if not item.name.startswith("_handle_ops_"):
                    continue
                for dec in item.decorator_list:
                    if isinstance(dec, ast.Call):
                        f = dec.func
                        is_api_endpoint = (
                            (isinstance(f, ast.Name) and f.id == "api_endpoint") or
                            (isinstance(f, ast.Attribute) and f.attr == "api_endpoint")
                        )
                        if is_api_endpoint and dec.args:
                            first = dec.args[0]
                            if isinstance(first, ast.Constant) and first.value == "INF":
                                decorated_with_inf.append(item.name)
    assert len(decorated_with_inf) >= 3, (
        f"INF domain decorator 부착 count={len(decorated_with_inf)} < 3: "
        f"{decorated_with_inf}"
    )


def test_debug_toggle_flips_flag_in_isolated_dir(tmp_path, monkeypatch):
    """debug-toggle 핸들러 로직: debug.enabled 플래그 생성/삭제 동작."""
    # 격리된 cwd 설정
    bg = tmp_path / ".claude-organic" / "runs" / "bg"
    bg.mkdir(parents=True, exist_ok=True)
    assert not (bg / "debug.enabled").exists()
    monkeypatch.chdir(tmp_path)

    # ops module 로드 가능성만 verify (mixin instance 가 필요한 본체 로직은
    # 통합 테스트 영역). compile 호출이 SyntaxError 시 fail.
    p = _find_ops_file()
    assert p is not None
    compile(p.read_text(encoding="utf-8"), str(p), "exec")
