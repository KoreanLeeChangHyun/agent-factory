"""Provider-neutral terminal process contract."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from board.server.channels.terminal_channel import TerminalSSEChannel
from board.server.processes.claude_process import ClaudeProcess, _validate_images
from board.server.processes.codex_process import CodexProcess


def validate_images(images: list) -> str | None:
    """Validate terminal image attachments for the active process."""
    return _validate_images(images)


@runtime_checkable
class BrainProcess(Protocol):
    """Terminal process interface used by board routes."""

    @property
    def status(self) -> str: ...

    @property
    def session_id(self) -> str: ...

    @property
    def model(self) -> str: ...

    @property
    def permission_mode(self) -> str: ...

    @property
    def awaiting_response(self) -> bool: ...

    @property
    def provider(self) -> str: ...

    @property
    def capabilities(self) -> dict[str, bool]: ...

    def spawn(
        self,
        extra_args: list[str] | None = None,
        env_extras: dict[str, str] | None = None,
    ) -> dict: ...

    def send_input(
        self,
        text: str,
        images: list[dict] | None = None,
        attachments: list[dict] | None = None,
    ) -> dict: ...

    def send_permission_response(
        self,
        request_id: str,
        decision: str,
        session_id: str | None = None,
    ) -> dict: ...

    def interrupt(self) -> dict: ...

    def kill(self) -> dict: ...

    def get_in_flight_snapshot(self) -> dict | None: ...

    def set_external_status(self, status: str) -> None: ...

    def set_session_id(self, session_id: str) -> None: ...

    def set_persist_file(self, persist_file: str | None) -> None: ...


class ClaudeBrainProcess:
    """BrainProcess adapter around the existing Claude terminal process."""

    def __init__(
        self,
        channel: TerminalSSEChannel,
        persist_file: str | None = None,
        process: ClaudeProcess | None = None,
    ) -> None:
        self._process = process or ClaudeProcess(channel, persist_file=persist_file)

    @property
    def status(self) -> str:
        return self._process.status

    @property
    def session_id(self) -> str:
        return self._process.session_id

    @property
    def model(self) -> str:
        return self._process._model

    @property
    def permission_mode(self) -> str:
        return self._process._permission_mode

    @property
    def awaiting_response(self) -> bool:
        return bool(getattr(self._process, "_awaiting_response", False))

    @property
    def provider(self) -> str:
        return "claude"

    @property
    def capabilities(self) -> dict[str, bool]:
        return {
            "resume": True,
            "attachments": True,
            "permission_prompts": True,
            "interrupt": True,
            "slash_commands": True,
            "multiple_inputs": True,
        }

    def spawn(
        self,
        extra_args: list[str] | None = None,
        env_extras: dict[str, str] | None = None,
    ) -> dict:
        return self._process.spawn(extra_args=extra_args, env_extras=env_extras)

    def send_input(
        self,
        text: str,
        images: list[dict] | None = None,
        attachments: list[dict] | None = None,
    ) -> dict:
        return self._process.send_input(text, images=images, attachments=attachments)

    def send_permission_response(
        self,
        request_id: str,
        decision: str,
        session_id: str | None = None,
    ) -> dict:
        return self._process.send_permission_response(request_id, decision, session_id)

    def interrupt(self) -> dict:
        return self._process.interrupt()

    def kill(self) -> dict:
        return self._process.kill()

    def get_in_flight_snapshot(self) -> dict | None:
        return self._process.get_in_flight_snapshot()

    def set_external_status(self, status: str) -> None:
        self._process.set_external_status(status)

    def set_session_id(self, session_id: str) -> None:
        self._process._session_id = session_id

    def set_persist_file(self, persist_file: str | None) -> None:
        self._process._persist_file = persist_file


def create_brain_process(
    channel: TerminalSSEChannel,
    provider: str = "claude",
    persist_file: str | None = None,
    *,
    codex_bin: str = "codex",
    codex_model: str | None = None,
    codex_profile: str | None = None,
    codex_sandbox: str = "workspace-write",
    cwd: str | None = None,
) -> BrainProcess:
    """Create the active terminal process for a provider.

    Claude remains the default live terminal. Codex is available as an
    experimental one-shot terminal process.
    """
    normalized = provider.strip().lower() if provider else "claude"
    if normalized == "codex":
        return CodexProcess(
            channel,
            persist_file=persist_file,
            codex_bin=codex_bin,
            model=codex_model,
            profile=codex_profile,
            sandbox=codex_sandbox,
            cwd=cwd,
        )
    return ClaudeBrainProcess(channel, persist_file=persist_file)
