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
    assert process.capabilities["resume"] is True
    assert process.capabilities["attachments"] is True
    assert process.capabilities["permission_prompts"] is True


def test_runtime_exposes_brain_process_compat_alias() -> None:
    from board.server.runtime import state
    from board.server.processes.brain_process import BrainProcess

    assert state.brain_process is state.claude_process
    assert isinstance(state.brain_process, BrainProcess)


def test_workflow_session_registry_uses_brain_process(tmp_path) -> None:
    from board.server.processes.brain_process import BrainProcess
    from board.server.sessions.workflow_session import WorkflowSessionRegistry

    registry = WorkflowSessionRegistry(persist_dir=str(tmp_path))
    session = registry.create("WR-100", "implement", "/tmp/work")

    assert isinstance(session.process, BrainProcess)
    assert session.process.status == "stopped"


def test_brain_process_factory_can_create_codex_process() -> None:
    from board.server.channels.terminal_channel import TerminalSSEChannel
    from board.server.processes.brain_process import create_brain_process
    from board.server.processes.codex_process import CodexProcess

    process = create_brain_process(TerminalSSEChannel(), provider="codex")

    assert isinstance(process, CodexProcess)
    assert process.status == "stopped"
    assert process.capabilities["resume"] is False
    assert process.capabilities["attachments"] is False
    assert process.capabilities["permission_prompts"] is False
    assert process.capabilities["interrupt"] is True
    assert process.capabilities["multiple_inputs"] is True


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


def test_codex_process_extracts_session_id_from_stdout_json() -> None:
    from board.server.processes.codex_process import CodexProcess, _event_session_id

    assert _event_session_id({"session_id": "session-top"}) == "session-top"
    assert _event_session_id({"thread": {"id": "thread-nested"}}) == "thread-nested"
    assert _event_session_id({"type": "session.created", "id": "session-event"}) == "session-event"

    class FakeChannel:
        def __init__(self) -> None:
            self.events: list[dict] = []

        def broadcast(self, data: dict) -> None:
            self.events.append(data)

    class FakeProcess:
        stdout = [
            '{"type":"session.created","id":"codex-session-1"}\n',
            '{"type":"message","text":"hello"}\n',
        ]
        returncode = 0

        def wait(self, timeout=None):
            return 0

    channel = FakeChannel()
    process = CodexProcess(channel)  # type: ignore[arg-type]
    process.set_session_id("codex-placeholder")
    process._process = FakeProcess()  # type: ignore[assignment]

    process._read_stdout_loop()

    assert process.session_id == "codex-session-1"
    assert channel.events[-2]["session_id"] == "codex-session-1"


def test_codex_process_resumes_finished_session_for_next_input(monkeypatch) -> None:
    from board.server.channels.terminal_channel import TerminalSSEChannel
    from board.server.processes import codex_process
    from board.server.processes.codex_process import CodexProcess

    captured: dict = {"writes": []}

    class FakeStdin:
        def write(self, text):
            captured["writes"].append(text)

        def close(self):
            captured["closed"] = True

    class FakePopen:
        stdout: list[str] = []
        returncode = 0

        def __init__(self, cmd, **kwargs):
            captured["cmd"] = cmd
            captured.update(kwargs)
            self.stdin = FakeStdin()

        def poll(self):
            return 0

        def wait(self, timeout=None):
            return 0

    monkeypatch.setattr(codex_process.subprocess, "Popen", FakePopen)

    process = CodexProcess(TerminalSSEChannel(), codex_bin="codex-test", model="gpt-test")
    process._codex_session_id = "codex-session-1"
    result = process.send_input("next prompt")
    if process._stdout_thread is not None:
        process._stdout_thread.join(timeout=1)

    assert result == {"ok": True, "error": ""}
    assert captured["cmd"] == [
        "codex-test",
        "exec",
        "resume",
        "--json",
        "--model",
        "gpt-test",
        "codex-session-1",
        "-",
    ]
    assert captured["writes"] == ["next prompt", "\n"]
    assert captured["closed"] is True


def test_terminal_provider_config_reads_settings(tmp_path, monkeypatch) -> None:
    from board.server.runtime.state import load_terminal_provider_config

    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("AGENT_FACTORY_LLM_PROVIDER", raising=False)
    settings_dir = tmp_path / ".agent-factory"
    settings_dir.mkdir()
    (settings_dir / ".settings").write_text(
        "LLM_PROVIDER=codex\n"
        "CODEX_BIN=codex-test\n"
        "CODEX_MODEL=gpt-test\n"
        "CODEX_PROFILE=work\n"
        "CODEX_SANDBOX=danger-full-access\n",
        encoding="utf-8",
    )

    config = load_terminal_provider_config(str(tmp_path))

    assert config.provider == "codex"
    assert config.codex_bin == "codex-test"
    assert config.codex_model == "gpt-test"
    assert config.codex_profile == "work"
    assert config.codex_sandbox == "danger-full-access"


def test_terminal_provider_config_accepts_legacy_provider_key(tmp_path, monkeypatch) -> None:
    from board.server.runtime.state import load_terminal_provider_config

    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("AGENT_FACTORY_LLM_PROVIDER", raising=False)
    settings_dir = tmp_path / ".agent-factory"
    settings_dir.mkdir()
    (settings_dir / ".settings").write_text("AGENT_FACTORY_LLM_PROVIDER=codex\n", encoding="utf-8")

    config = load_terminal_provider_config(str(tmp_path))

    assert config.provider == "codex"


def test_configure_brain_process_switches_stopped_terminal_to_codex(tmp_path, monkeypatch) -> None:
    from board.server.runtime import state
    from board.server.processes.codex_process import CodexProcess

    original_brain = state.brain_process
    original_alias = state.claude_process
    try:
        settings_dir = tmp_path / ".agent-factory"
        settings_dir.mkdir()
        (settings_dir / ".settings").write_text(
            "LLM_PROVIDER=codex\nCODEX_BIN=codex-test\n",
            encoding="utf-8",
        )

        process = state.configure_brain_process(str(tmp_path))

        assert isinstance(process, CodexProcess)
        assert state.brain_process is process
        assert state.claude_process is process
        assert process.provider == "codex"
    finally:
        state.brain_process = original_brain
        state.claude_process = original_alias


def test_configure_brain_process_switches_idle_terminal_provider(tmp_path, monkeypatch) -> None:
    from board.server.runtime import state
    from board.server.processes.codex_process import CodexProcess

    class IdleBrain:
        provider = "claude"
        status = "idle"
        awaiting_response = False
        killed = False

        def set_persist_file(self, persist_file):
            self.persist_file = persist_file

        def kill(self):
            self.killed = True
            self.status = "stopped"
            return {"ok": True, "error": ""}

    original_brain = state.brain_process
    original_alias = state.claude_process
    idle_brain = IdleBrain()
    try:
        settings_dir = tmp_path / ".agent-factory"
        settings_dir.mkdir()
        (settings_dir / ".settings").write_text(
            "LLM_PROVIDER=codex\nCODEX_BIN=codex-test\n",
            encoding="utf-8",
        )

        state.brain_process = idle_brain  # type: ignore[assignment]
        state.claude_process = idle_brain  # type: ignore[assignment]
        process = state.configure_brain_process(str(tmp_path))

        assert idle_brain.killed is True
        assert isinstance(process, CodexProcess)
        assert state.brain_process is process
        assert state.claude_process is process
    finally:
        state.brain_process = original_brain
        state.claude_process = original_alias


def test_configure_brain_process_keeps_running_terminal_provider(tmp_path) -> None:
    from board.server.runtime import state

    class RunningBrain:
        provider = "claude"
        status = "running"
        awaiting_response = True
        killed = False

        def set_persist_file(self, persist_file):
            self.persist_file = persist_file

        def kill(self):
            self.killed = True
            return {"ok": True, "error": ""}

    original_brain = state.brain_process
    original_alias = state.claude_process
    running_brain = RunningBrain()
    try:
        settings_dir = tmp_path / ".agent-factory"
        settings_dir.mkdir()
        (settings_dir / ".settings").write_text(
            "LLM_PROVIDER=codex\nCODEX_BIN=codex-test\n",
            encoding="utf-8",
        )

        state.brain_process = running_brain  # type: ignore[assignment]
        state.claude_process = running_brain  # type: ignore[assignment]
        process = state.configure_brain_process(str(tmp_path))

        assert process is running_brain
        assert running_brain.killed is False
        assert running_brain.persist_file == str(tmp_path / ".agent-factory" / ".last-session-id")
    finally:
        state.brain_process = original_brain
        state.claude_process = original_alias
