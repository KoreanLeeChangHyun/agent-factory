"""Board API Conveyor app-boundary coverage."""

from __future__ import annotations


def test_conveyor_compat_exports_match_app_boundary() -> None:
    from board.server.handlers import conveyor as compat
    from engine.apps.board_api import conveyor as app

    assert compat.ConveyorHandlerMixin is app.ConveyorHandlerMixin
    assert compat._emit_launch_event is app._emit_launch_event


def test_conveyor_handler_exposes_router_methods() -> None:
    from engine.apps.board_api.conveyor import ConveyorHandlerMixin

    expected = [
        "_handle_conveyor_branch_active",
        "_handle_conveyor_workflow_entries",
        "_handle_conveyor_workflow_detail",
        "_handle_conveyor_move",
        "_handle_conveyor_workrequest",
        "_handle_conveyor_submit",
        "_handle_conveyor_complete",
        "_handle_conveyor_delete",
        "_handle_conveyor_branch_toggle",
        "_handle_conveyor_undo_complete",
    ]

    missing = [name for name in expected if not hasattr(ConveyorHandlerMixin, name)]
    assert missing == []
