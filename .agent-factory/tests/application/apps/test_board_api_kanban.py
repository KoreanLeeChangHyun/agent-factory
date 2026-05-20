"""Board API Kanban app-boundary coverage."""

from __future__ import annotations


def test_kanban_compat_exports_match_app_boundary() -> None:
    from board.server.handlers import kanban as compat
    from engine.apps.board_api import kanban as app

    assert compat.KanbanHandlerMixin is app.KanbanHandlerMixin
    assert compat._emit_launch_event is app._emit_launch_event


def test_kanban_handler_exposes_router_methods() -> None:
    from engine.apps.board_api.kanban import KanbanHandlerMixin

    expected = [
        "_handle_kanban_branch_active",
        "_handle_kanban_workflow_entries",
        "_handle_kanban_workflow_detail",
        "_handle_kanban_move",
        "_handle_kanban_workrequest",
        "_handle_kanban_submit",
        "_handle_kanban_done",
        "_handle_kanban_delete",
        "_handle_kanban_branch_toggle",
        "_handle_kanban_undo_done",
    ]

    missing = [name for name in expected if not hasattr(KanbanHandlerMixin, name)]
    assert missing == []
