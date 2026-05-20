"""Board API terminal app-boundary coverage."""

from __future__ import annotations


def test_terminal_compat_export_matches_app_boundary() -> None:
    from board.server.handlers.terminal import TerminalHandlerMixin as compat
    from engine.apps.board_api.terminal import TerminalHandlerMixin as app

    assert compat is app


def test_terminal_handler_exposes_router_methods() -> None:
    from engine.apps.board_api.terminal import TerminalHandlerMixin

    expected = [
        "_handle_terminal_sse",
        "_handle_terminal_status",
        "_handle_terminal_sessions",
        "_handle_terminal_history",
        "_handle_terminal_start",
        "_handle_terminal_input",
        "_handle_terminal_interrupt",
        "_handle_terminal_kill",
        "_handle_terminal_command",
        "_handle_terminal_permission",
    ]

    missing = [name for name in expected if not hasattr(TerminalHandlerMixin, name)]
    assert missing == []
