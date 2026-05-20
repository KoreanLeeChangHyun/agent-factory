"""Board API Kanban done helper app-boundary coverage."""

from __future__ import annotations


def test_kanban_done_re_compat_exports_match_app_boundary() -> None:
    from board.server.handlers import _kanban_done_re as compat
    from engine.apps.board_api import kanban_done_re as app

    assert compat._classify_done_failure is app._classify_done_failure
    assert compat._DONE_MERGE_OK_RE is app._DONE_MERGE_OK_RE
    assert compat._UNDO_WORKTREE_RE is app._UNDO_WORKTREE_RE


def test_kanban_done_helper_compat_exports_match_app_boundary() -> None:
    from board.server.handlers import _kanban_done_helpers as compat
    from engine.apps.board_api import kanban_done_helpers as app

    assert compat.handle_kanban_done_force is app.handle_kanban_done_force
    assert compat.handle_kanban_done_review is app.handle_kanban_done_review
    assert compat.check_derived_blocked is app.check_derived_blocked
