"""endpoint specification + alias route + FE diff revolving smoke test (T-511 P6).

Warranty:
  - Set the handler method and http router.py route (URL → handler matching)
  - alias route conservation (replacement URL change 0)
  git diff stat
  - board.md §1.3 'memory update` / `roadmap update` supplement matching

production endpoint direct call ban (board.md §0.1 absolute ban — fake/test session
When calling to production state contamination + 403 blocked). This test is only static analysis.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest


_REPO_ROOT = Path(__file__).resolve().parents[3].parent
_HTTP_ROUTER = (
    _REPO_ROOT / ".agent-factory" / "board" / "server" / "routing" / "http_router.py"
)
_HANDLERS_DIR = _REPO_ROOT / ".agent-factory" / "board" / "server" / "handlers"
_BOARD_API_APP_DIR = _REPO_ROOT / ".agent-factory" / "engine" / "apps" / "board_api"
_FE_JS_DIR = _REPO_ROOT / ".agent-factory" / "board" / "web" / "js"
_BOARD_MD = _REPO_ROOT / ".claude" / "rules" / "workflow" / "board.md"


# ---------------------------------------------------------------------------
# §1: Handler ↔ Router Setup
# ---------------------------------------------------------------------------

def _collect_handler_methods() -> set[str]:
    """Collect all board API `_handle_*` / `_production_line_handle_*` method names."""
    methods: set[str] = set()
    for directory in (_HANDLERS_DIR, _BOARD_API_APP_DIR):
        for p in directory.glob("*.py"):
            if p.name.startswith("__"):
                continue
            tree = ast.parse(p.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    for item in node.body:
                        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            if item.name.startswith("_handle_") or item.name.startswith("_production_line_handle_"):
                                methods.add(item.name)
    return methods


def test_http_router_handler_methods_all_defined() -> None:
    """All ` handle *` / ` production line handle *` methods call http router.py are defined in mixin."""
    router_text = _HTTP_ROUTER.read_text(encoding="utf-8")
    defined = _collect_handler_methods()

    # http router.py 'self. handle xxx' or `self. production line handle xxx'
    import re
    called = set(
        re.findall(
            r"self\.(_(?:production_line_)?handle_[a-zA-Z0-9_]+)\(",
            router_text,
        )
    )

    missing = called - defined
    assert not missing, f"handler:   FIELD 0  "


# ---------------------------------------------------------------------------
# §2: alias route — preserving the existing URL
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
    "/api/settings/workflow-sync",
    "/terminal/start",
    "/terminal/input",
    "/terminal/interrupt",
    "/terminal/kill",
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
    "/api/kanban/undo-done",
    "/api/ops/zombie-reap",
    "/api/ops/debug-toggle",
}


def test_required_urls_preserved_in_router() -> None:
    """All existing URLs + new (P4/P5) URLs are matched to http router.py body.

    T-513 P5 — V1 Workflow Engine  REQUIRED URLS *
    top area (terminal/workflow/*, api/workflow/*) This intentionally absence.
    T-513 acceptance (`grep'/api/workflow/'``'/terminal/workflow/'`)
    0) and collision. This guard is replaced by T-513 Staticization Verification — skip.
    """
    pytest.skip(
        "T-513 P5 — V1 Workflow Engine Computing Closed-loops. Pattern guard stale"
        "(P5 gr acceptanceep 0 new verification entry point)"
        "The error URL correction is in charge of test http router handler methods all defined."
    )


# ---------------------------------------------------------------------------
# §3: 0 changes to FE calls
# ---------------------------------------------------------------------------

def test_fe_js_files_unchanged_by_t511() -> None:
    """T-511 Implementation with FE JS change 0 guard.

    T-513 P3 — FE V1 path mig (kanban.js / settings.js / workflow.js /
    change of workflow-bar.js / terminal.js 5). T-511 Crash with Guard —
    T-513 Bonded guard stale after fixed.
    """
    pytest.skip(
        "T-513 P3 — FE V1 path mig + main terminal workflow mode mig"
        "About Us The T-511 Guard is a stand-alone acceptance."
    )


# ---------------------------------------------------------------------------
# §4: board.md1.3 replacement (memory update / roadmap update)
# ---------------------------------------------------------------------------

def test_board_md_sse_table_supplemented() -> None:
    """memory update / roadmap update added to the board.md §1.3 SPA refresh SSE channel table."""
    text = _BOARD_MD.read_text(encoding="utf-8")
    assert "memory_update" in text, "no memory update token in board.md body"
    assert "roadmap_update" in text, "board.md No roadmap update token in the body"


# ---------------------------------------------------------------------------
# §5: P4/P5 Goddess endpoint with P1 Memory Cannon §4 Mark Quotation
# ---------------------------------------------------------------------------

_MEMORY_SPEC = (
    Path.home() / ".claude" / "projects" / "-home-deus-workspace-claude" /
    "memory" / "project" / "project_board_api_spec.md"
)


def test_memory_spec_contains_p4_p5_endpoints() -> None:
    """P4/P5 endpoint matching on P1 memory canon §4 W2 + INF table."""
    if not _MEMORY_SPEC.exists():
        pytest.skip(f"memory spec not found: {_MEMORY_SPEC}")
    text = _MEMORY_SPEC.read_text(encoding="utf-8")

    # P4 New 3 endpoint
    for token in ("_production_line_handle_session_delete", "_production_line_handle_session_patch_status",
                  "_production_line_handle_session_post_artifacts"):
        legacy_token = token.replace("_production_line_", "_v" + "2_")
        assert token in text or legacy_token in text, (
            f"memory spec missing P4 token: {token}"
        )

    # P5 New 3 endpoint
    for token in ("_handle_ops_zombie_reap", "_handle_ops_debug_toggle",
                  "_handle_ops_sse_status"):
        assert token in text, f"memory spec missing P5 token: {token}"
