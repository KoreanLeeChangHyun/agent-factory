"""endpoint 명세 + alias route + FE diff 회귀 smoke 테스트 (T-511 P6).

검증:
  - handler 메서드와 http_router.py 라우팅이 정합 (URL → handler 매칭)
  - alias route 보존 (기존 URL 변경 0건)
  - FE 호출부 변경 0건 (`.claude-organic/board/static/js/` git diff stat)
  - board.md §1.3 의 `memory_update` / `roadmap_update` 보충 매칭

production endpoint 직접 호출 금지 (board.md §0.1 절대 금지 — fake/test session
으로 호출 시 production state 오염 + 403 차단). 본 테스트는 정적 분석만.
"""

from __future__ import annotations

import ast
import subprocess
from pathlib import Path

import pytest


_REPO_ROOT = Path(__file__).resolve().parents[4]
_HTTP_ROUTER = _REPO_ROOT / ".claude-organic" / "board" / "server" / "http_router.py"
_HANDLERS_DIR = _REPO_ROOT / ".claude-organic" / "board" / "server" / "handlers"
_FE_JS_DIR = _REPO_ROOT / ".claude-organic" / "board" / "static" / "js"
_BOARD_MD = _REPO_ROOT / ".claude" / "rules" / "workflow" / "board.md"


# ---------------------------------------------------------------------------
# §1: handler ↔ router 정합
# ---------------------------------------------------------------------------

def _collect_handler_methods() -> set[str]:
    """handlers/ 하위 모든 `_handle_*` / `_v2_handle_*` 메서드 이름 수집."""
    methods: set[str] = set()
    for p in _HANDLERS_DIR.glob("*.py"):
        if p.name.startswith("__"):
            continue
        tree = ast.parse(p.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if item.name.startswith("_handle_") or item.name.startswith("_v2_handle_"):
                            methods.add(item.name)
    return methods


def test_http_router_handler_methods_all_defined() -> None:
    """http_router.py 가 호출하는 모든 `_handle_*` / `_v2_handle_*` 메서드가 mixin 에 정의됨."""
    router_text = _HTTP_ROUTER.read_text(encoding="utf-8")
    defined = _collect_handler_methods()

    # http_router.py 본문에서 `self._handle_xxx(` 또는 `self._v2_handle_xxx(` 형태 추출
    import re
    called = set(re.findall(r"self\.(_(?:v2_)?handle_[a-zA-Z0-9_]+)\(", router_text))

    missing = called - defined
    assert not missing, f"http_router.py 가 호출하는 미정의 handler: {missing}"


# ---------------------------------------------------------------------------
# §2: alias route — 기존 URL 보존
# ---------------------------------------------------------------------------

_REQUIRED_URLS_GET = {
    "/events",
    "/poll",
    "/terminal/events",
    "/terminal/status",
    "/terminal/sessions",
    "/terminal/history",
    "/terminal/workflow/status",
    "/terminal/workflow/events",
    "/terminal/workflow/list",
    "/terminal/workflow/history",
    "/api/kanban/branch/active",
    "/api/v2/sessions",
    "/api/ops/sse-status",
}

_REQUIRED_URLS_POST = {
    "/api/env",
    "/api/restart",
    "/api/debug-log",
    "/api/workflow/sync",
    "/terminal/start",
    "/terminal/input",
    "/terminal/interrupt",
    "/terminal/kill",
    "/terminal/workflow/start",
    "/terminal/workflow/kill",
    "/api/workflow/stop",
    "/terminal/workflow/input",
    "/terminal/workflow/step",
    "/terminal/command",
    "/terminal/permission",
    "/api/memory/file",
    "/api/prompt/rules/file",
    "/api/prompt/prompt-files/file",
    "/api/prompt/claude-md",
    "/api/quick-prompts/item",
    "/api/memory/gc/run",
    "/api/memory/gc/prune-archive",
    "/api/kanban/move",
    "/api/kanban/submit",
    "/api/kanban/done",
    "/api/kanban/delete",
    "/api/kanban/branch/toggle",
    "/api/kanban/worktree-commit",
    "/api/workflow/undo-done",
    "/api/ops/zombie-reap",
    "/api/ops/debug-toggle",
}


def test_required_urls_preserved_in_router() -> None:
    """기존 URL + 신규 (P4/P5) URL 모두 http_router.py 본문에 매칭."""
    router_text = _HTTP_ROUTER.read_text(encoding="utf-8")
    missing: list[str] = []
    for url in _REQUIRED_URLS_GET | _REQUIRED_URLS_POST:
        if url not in router_text:
            missing.append(url)
    assert not missing, f"router missing URLs: {missing}"


# ---------------------------------------------------------------------------
# §3: FE 호출부 변경 0건
# ---------------------------------------------------------------------------

def test_fe_js_files_unchanged_by_t511() -> None:
    """T-511 본 implement 가 `.claude-organic/board/static/js/` 변경 0건.

    검증 범위: T-511 작업으로 발생한 변경만. 본 워크트리 base 와 비교 (HEAD)
    + 워크트리 base 가 develop 보다 이전 commit 이어도 develop 가 한참 앞서간
    상황 (다른 티켓 머지) 의 FE 변경은 본 티켓 범위 밖이므로 제외.

    사용자 결정 #6 (T-510 §6) — FE 호출부 시그니처 변경 0건 의무.
    """
    if not _FE_JS_DIR.exists():
        pytest.skip(f"FE JS dir not found: {_FE_JS_DIR}")

    # (a) working tree + staged 변경 검사 — T-511 작업으로 추가/수정된 FE 파일 0건
    try:
        r = subprocess.run(
            ["git", "status", "--porcelain", "--", str(_FE_JS_DIR)],
            cwd=str(_REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        pytest.skip(f"git status 실행 실패: {exc}")

    status_lines = [ln for ln in (r.stdout or "").splitlines() if ln.strip()]
    if status_lines:
        pytest.fail(
            "T-511 가 FE JS 파일 변경 (사용자 결정 #6 위반):\n" +
            "\n".join(status_lines)
        )

    # (b) 본 worktree branch HEAD 와 본 branch base 사이의 commit 들 중 FE 파일
    #     변경이 0 건임을 확인. base = merge-base(HEAD, develop)
    try:
        base = subprocess.run(
            ["git", "merge-base", "HEAD", "develop"],
            cwd=str(_REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if base.returncode != 0 or not base.stdout.strip():
            pytest.skip("merge-base 계산 실패")
        base_sha = base.stdout.strip()
        diff = subprocess.run(
            ["git", "diff", "--stat", base_sha, "HEAD", "--", str(_FE_JS_DIR)],
            cwd=str(_REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        pytest.skip(f"git diff 실행 실패: {exc}")

    output = (diff.stdout or "").strip()
    if output:
        pytest.fail(
            "T-511 branch 의 FE JS 호출부 변경 감지 (사용자 결정 #6 위반):\n" +
            output
        )


# ---------------------------------------------------------------------------
# §4: board.md §1.3 보충 (memory_update / roadmap_update)
# ---------------------------------------------------------------------------

def test_board_md_sse_table_supplemented() -> None:
    """board.md §1.3 SPA refresh SSE 채널 표에 memory_update / roadmap_update 추가됨."""
    text = _BOARD_MD.read_text(encoding="utf-8")
    assert "memory_update" in text, "board.md 본문에 memory_update 토큰 없음"
    assert "roadmap_update" in text, "board.md 본문에 roadmap_update 토큰 없음"


# ---------------------------------------------------------------------------
# §5: P4/P5 신설 endpoint 가 P1 메모리 캐논 §4 표 인용과 정합
# ---------------------------------------------------------------------------

_MEMORY_SPEC = (
    Path.home() / ".claude" / "projects" / "-home-deus-workspace-claude" /
    "memory" / "project" / "project_board_api_spec.md"
)


def test_memory_spec_contains_p4_p5_endpoints() -> None:
    """P1 메모리 캐논 §4 의 W2 + INF 표에 P4/P5 endpoint 매칭."""
    if not _MEMORY_SPEC.exists():
        pytest.skip(f"memory spec not found: {_MEMORY_SPEC}")
    text = _MEMORY_SPEC.read_text(encoding="utf-8")

    # P4 신설 3 endpoint
    for token in ("_v2_handle_session_delete", "_v2_handle_session_patch_status",
                  "_v2_handle_session_post_artifacts"):
        assert token in text, f"memory spec missing P4 token: {token}"

    # P5 신설 3 endpoint
    for token in ("_handle_ops_zombie_reap", "_handle_ops_debug_toggle",
                  "_handle_ops_sse_status"):
        assert token in text, f"memory spec missing P5 token: {token}"
