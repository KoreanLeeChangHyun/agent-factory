"""Board API Kanban done helper app-boundary coverage."""

from __future__ import annotations


def test_conveyor_complete_re_compat_exports_match_app_boundary() -> None:
    from board.server.handlers import _conveyor_complete_re as compat
    from engine.apps.board_api import conveyor_complete_re as app

    assert compat._classify_done_failure is app._classify_done_failure
    assert compat._DONE_MERGE_OK_RE is app._DONE_MERGE_OK_RE
    assert compat._UNDO_WORKTREE_RE is app._UNDO_WORKTREE_RE


def test_conveyor_complete_helper_compat_exports_match_app_boundary() -> None:
    from board.server.handlers import _conveyor_complete_helpers as compat
    from engine.apps.board_api import conveyor_complete_helpers as app

    assert compat.handle_conveyor_complete_force is app.handle_conveyor_complete_force
    assert compat.handle_conveyor_complete_review is app.handle_conveyor_complete_review
    assert compat.check_derived_blocked is app.check_derived_blocked
