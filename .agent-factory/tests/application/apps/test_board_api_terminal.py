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


def test_brain_process_factory_can_create_codex_process() -> None:
    from board.server.channels.terminal_channel import TerminalSSEChannel
    from board.server.processes.brain_process import create_brain_process
    from board.server.processes.codex_process import CodexProcess

    process = create_brain_process(TerminalSSEChannel(), provider="codex")

    assert isinstance(process, CodexProcess)
    assert process.status == "stopped"


def test_codex_process_spawn_builds_exec_command(monkeypatch, tmp_path) -> None:
    from board.server.channels.terminal_channel import TerminalSSEChannel
    from board.server.processes import codex_process
    from board.server.processes.codex_process import CodexProcess

    captured: dict = {}

    class FakePopen:
        stdout: list[str] = []
        stdin = None
        returncode = 0

        def __init__(self, cmd, **kwargs):
            captured["cmd"] = cmd
            captured.update(kwargs)

        def poll(self):
            return 0

        def wait(self, timeout=None):
            return 0

    monkeypatch.setattr(codex_process.subprocess, "Popen", FakePopen)

    process = CodexProcess(
        TerminalSSEChannel(),
        codex_bin="codex-test",
        model="gpt-test",
        profile="work",
        sandbox="danger-full-access",
        cwd=str(tmp_path),
    )
    result = process.spawn(["--skip-git-repo-check"])
    if process._stdout_thread is not None:
        process._stdout_thread.join(timeout=1)

    assert result["ok"]
    assert captured["cmd"] == [
        "codex-test",
        "exec",
        "--json",
        "--cd",
        str(tmp_path),
        "--model",
        "gpt-test",
        "--profile",
        "work",
        "--sandbox",
        "danger-full-access",
        "--skip-git-repo-check",
        "-",
    ]
    assert captured["cwd"] == str(tmp_path)


def test_codex_process_maps_stdout_json_to_terminal_events() -> None:
    from board.server.processes.codex_process import CodexProcess

    class FakeChannel:
        def __init__(self) -> None:
            self.events: list[dict] = []

        def broadcast(self, data: dict) -> None:
            self.events.append(data)

    class FakeProcess:
        stdout = [
            '{"type":"message","text":"hello"}\n',
            '{"type":"result","message":" done"}\n',
        ]
        returncode = 0

        def wait(self, timeout=None):
            return 0

    channel = FakeChannel()
    process = CodexProcess(channel)  # type: ignore[arg-type]
    process.set_session_id("codex-test-session")
    process._process = FakeProcess()  # type: ignore[assignment]

    process._read_stdout_loop()

    text_events = [event for event in channel.events if event.get("type") == "stream_event"]
    assert [event["event"]["delta"]["text"] for event in text_events] == ["hello", " done"]
    assert channel.events[-2]["type"] == "result"
    assert channel.events[-2]["result"] == "hello done"
    assert channel.events[-1]["subtype"] == "process_exit"
