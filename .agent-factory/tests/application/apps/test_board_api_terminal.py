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


def test_brain_process_factory_wraps_claude_process() -> None:
    from board.server.channels.terminal_channel import TerminalSSEChannel
    from board.server.processes.brain_process import ClaudeBrainProcess, create_brain_process
    from board.server.processes.claude_process import ClaudeProcess

    process = create_brain_process(TerminalSSEChannel())

    assert isinstance(process, ClaudeBrainProcess)
    assert not isinstance(process, ClaudeProcess)
    assert process.status == "stopped"

    process.set_session_id("session-123")
    assert process.session_id == "session-123"


def test_runtime_exposes_brain_process_compat_alias() -> None:
    from board.server.runtime import state
    from board.server.processes.brain_process import BrainProcess

    assert state.brain_process is state.claude_process
    assert isinstance(state.brain_process, BrainProcess)


def test_workflow_session_registry_uses_brain_process(tmp_path) -> None:
    from board.server.processes.brain_process import BrainProcess
    from board.server.sessions.workflow_session import WorkflowSessionRegistry

    registry = WorkflowSessionRegistry(persist_dir=str(tmp_path))
    session = registry.create("T-100", "implement", "/tmp/work")

    assert isinstance(session.process, BrainProcess)
    assert session.process.status == "stopped"
