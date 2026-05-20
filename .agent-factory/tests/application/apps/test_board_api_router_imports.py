"""Board HTTP router uses app-boundary Board API handlers."""

from __future__ import annotations


def test_board_http_router_composes_app_boundary_mixins() -> None:
    from board.server.http_router import BoardHTTPRequestHandler
    from engine.apps.board_api.files import FilesHandlerMixin
    from engine.apps.board_api.generic import GenericHandlerMixin
    from engine.apps.board_api.kanban import KanbanHandlerMixin
    from engine.apps.board_api.memory_gc import MemoryGcHandlerMixin
    from engine.apps.board_api.metrics import MetricsHandlerMixin
    from engine.apps.board_api.ops_endpoints import OpsHandlerMixin
    from engine.apps.board_api.settings import SettingsHandlerMixin
    from engine.apps.board_api.sync import SyncHandlerMixin
    from engine.apps.board_api.terminal import TerminalHandlerMixin
    from engine.apps.board_api.production_line_workflow import V2WorkflowHandlerMixin
    from engine.apps.board_api.worktree_commit import WorktreeCommitHandlerMixin

    expected = [
        TerminalHandlerMixin,
        V2WorkflowHandlerMixin,
        KanbanHandlerMixin,
        MetricsHandlerMixin,
        MemoryGcHandlerMixin,
        WorktreeCommitHandlerMixin,
        OpsHandlerMixin,
        FilesHandlerMixin,
        GenericHandlerMixin,
        SyncHandlerMixin,
        SettingsHandlerMixin,
    ]

    assert list(BoardHTTPRequestHandler.__mro__[1:12]) == expected
