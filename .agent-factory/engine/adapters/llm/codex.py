"""Codex CLI implementation of the LLMAdapter contract."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from engine.core.ports.llm import EventHandler, LLMEvent, LLMRequest, LLMResult


CODEX_BIN = "codex"
DEFAULT_SANDBOX = "workspace-write"
DEFAULT_APPROVAL_POLICY = "never"


def _combined_prompt(request: LLMRequest) -> str:
    if not request.system_prompt:
        return request.prompt
    return f"{request.system_prompt}\n\n{request.prompt}"


def _event_text(obj: dict[str, Any]) -> str:
    for key in ("text", "message", "content", "delta"):
        value = obj.get(key)
        if isinstance(value, str):
            return value
    item = obj.get("item")
    if isinstance(item, dict):
        for key in ("text", "message", "content"):
            value = item.get(key)
            if isinstance(value, str):
                return value
    return ""


def _event_session_id(obj: dict[str, Any]) -> str:
    for key in ("thread_id", "threadId", "session_id", "sessionId", "conversation_id", "conversationId"):
        value = obj.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    for key in ("thread", "session", "conversation", "metadata"):
        value = obj.get(key)
        if not isinstance(value, dict):
            continue
        for nested_key in ("id", "thread_id", "threadId", "session_id", "sessionId"):
            nested_value = value.get(nested_key)
            if isinstance(nested_value, str) and nested_value.strip():
                return nested_value.strip()
    return ""


def _config_override(key: str, value: str) -> str:
    return f"{key}={json.dumps(value)}"


@dataclass(frozen=True)
class CodexAdapter:
    """Adapter for `codex exec` non-interactive runs."""

    codex_bin: str = CODEX_BIN
    model: str | None = None
    profile: str | None = None
    sandbox: str = DEFAULT_SANDBOX
    approval_policy: str = DEFAULT_APPROVAL_POLICY
    add_dirs: tuple[Path, ...] = ()
    extra_args: tuple[str, ...] = field(default_factory=tuple)
    use_json_events: bool = True

    def complete(
        self,
        request: LLMRequest,
        *,
        on_event: EventHandler | None = None,
    ) -> LLMResult:
        cmd = self._build_command(request)
        try:
            proc = subprocess.run(
                cmd,
                input=_combined_prompt(request),
                capture_output=True,
                text=True,
                cwd=str(request.cwd) if request.cwd else None,
                timeout=request.timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return LLMResult(
                ok=False,
                output_text=exc.stdout or "",
                error=exc.stderr or "codex exec timed out",
                timed_out=True,
                returncode=-1,
                session_id=request.session_id,
                metadata={"provider": "codex", "command": cmd},
            )
        except (FileNotFoundError, OSError) as exc:
            return LLMResult(
                ok=False,
                error=f"codex spawn failed: {exc}",
                returncode=-1,
                session_id=request.session_id,
                metadata={"provider": "codex", "command": cmd},
            )

        events, output_text, codex_session_id = self._parse_stdout(proc.stdout, on_event=on_event)
        metadata: dict[str, Any] = {"provider": "codex", "command": cmd}
        if codex_session_id:
            metadata["codex_session_id"] = codex_session_id
        return LLMResult(
            ok=proc.returncode == 0,
            output_text=output_text,
            error=proc.stderr,
            returncode=proc.returncode,
            session_id=request.session_id,
            events=events,
            metadata=metadata,
        )

    def _build_command(self, request: LLMRequest) -> list[str]:
        cmd = [self.codex_bin, "exec"]
        if self.approval_policy:
            cmd += ["-c", _config_override("approval_policy", self.approval_policy)]
        if self.use_json_events:
            cmd.append("--json")
        if request.cwd is not None:
            cmd += ["--cd", str(request.cwd)]
        if self.model:
            cmd += ["--model", self.model]
        if self.profile:
            cmd += ["--profile", self.profile]
        if self.sandbox:
            cmd += ["--sandbox", self.sandbox]
        for path in self.add_dirs:
            cmd += ["--add-dir", str(path)]
        cmd += list(self.extra_args)
        cmd.append("-")
        return cmd

    def _parse_stdout(
        self,
        stdout: str,
        *,
        on_event: EventHandler | None,
    ) -> tuple[list[LLMEvent], str, str]:
        if not self.use_json_events:
            event = LLMEvent(type="stdout", text=stdout)
            if on_event is not None:
                on_event(event)
            return [event], stdout, ""

        events: list[LLMEvent] = []
        text_parts: list[str] = []
        codex_session_id = ""
        for line in stdout.splitlines():
            if not line.strip():
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError:
                raw = {"type": "stdout", "text": line}
            if not isinstance(raw, dict):
                raw = {"type": "stdout", "text": str(raw)}
            session_id = _event_session_id(raw)
            if session_id:
                codex_session_id = session_id
            text = _event_text(raw)
            event = LLMEvent(type=str(raw.get("type") or "event"), text=text, raw=raw)
            events.append(event)
            if text:
                text_parts.append(text)
            if on_event is not None:
                on_event(event)
        output_text = "".join(text_parts) if text_parts else stdout
        return events, output_text, codex_session_id
