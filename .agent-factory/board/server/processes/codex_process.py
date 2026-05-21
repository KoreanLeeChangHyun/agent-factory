"""CodexProcess — minimal Codex CLI terminal process adapter."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import threading
import uuid
from pathlib import Path
from typing import Any

from board.server.channels.terminal_channel import TerminalSSEChannel
from board.server.support.common import logger, server_debug_log


def _event_text(data: dict[str, Any]) -> str:
    """Extract display text from known Codex JSON event shapes."""
    for key in ("text", "message", "content", "delta"):
        value = data.get(key)
        if isinstance(value, str):
            return value
    item = data.get("item")
    if isinstance(item, dict):
        for key in ("text", "message", "content"):
            value = item.get(key)
            if isinstance(value, str):
                return value
    return ""


class CodexProcess:
    """One-shot `codex exec --json -` process normalized to terminal SSE events."""

    provider = "codex"

    def __init__(
        self,
        channel: TerminalSSEChannel,
        persist_file: str | None = None,
        *,
        codex_bin: str = "codex",
        model: str | None = None,
        profile: str | None = None,
        sandbox: str = "workspace-write",
        cwd: str | None = None,
    ) -> None:
        self._process: subprocess.Popen | None = None
        self._session_id = ""
        self._model = model or ""
        self._permission_mode = ""
        self._status = "stopped"
        self._stdin_lock = threading.Lock()
        self._stdout_thread: threading.Thread | None = None
        self._channel = channel
        self._persist_file = persist_file
        self._awaiting_response = False
        self._codex_bin = codex_bin
        self._profile = profile
        self._sandbox = sandbox
        self._cwd = cwd
        self._stdin_closed = False

    @property
    def status(self) -> str:
        if not self._process:
            return self._status
        if self._process.poll() is None:
            return self._status
        return self._status

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def model(self) -> str:
        return self._model

    @property
    def permission_mode(self) -> str:
        return self._permission_mode

    @property
    def awaiting_response(self) -> bool:
        return self._awaiting_response

    def spawn(
        self,
        extra_args: list[str] | None = None,
        env_extras: dict[str, str] | None = None,
    ) -> dict:
        if self._process and self._process.poll() is None:
            self.kill()
        if self._stdout_thread and self._stdout_thread.is_alive():
            self._stdout_thread.join(timeout=3)

        self._session_id = f"codex-{uuid.uuid4()}"
        self._stdin_closed = False
        self._awaiting_response = False

        cmd = self._build_command(extra_args or [])
        proc_env = {**os.environ, **env_extras} if env_extras else None
        try:
            self._process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                bufsize=1,
                cwd=self._cwd,
                env=proc_env,
            )
        except FileNotFoundError:
            self._status = "stopped"
            return {"ok": False, "session_id": "", "error": "codex CLI not found in PATH"}
        except OSError as exc:
            self._status = "stopped"
            return {"ok": False, "session_id": "", "error": str(exc)}

        self._status = "running"
        self._persist_session_id()
        self._channel.broadcast({
            "type": "system",
            "subtype": "init",
            "session_id": self._session_id,
            "model": self._model,
            "permissionMode": self._permission_mode,
        })

        self._stdout_thread = threading.Thread(
            target=self._read_stdout_loop,
            daemon=True,
            name="codex-stdout-reader",
        )
        self._stdout_thread.start()
        return {"ok": True, "session_id": self._session_id, "error": ""}

    def _build_command(self, extra_args: list[str]) -> list[str]:
        cmd = [self._codex_bin, "exec", "--json"]
        if self._cwd:
            cmd += ["--cd", self._cwd]
        if self._model:
            cmd += ["--model", self._model]
        if self._profile:
            cmd += ["--profile", self._profile]
        if self._sandbox:
            cmd += ["--sandbox", self._sandbox]
        cmd += extra_args
        cmd.append("-")
        return cmd

    def send_input(
        self,
        text: str,
        images: list[dict] | None = None,
        attachments: list[dict] | None = None,
    ) -> dict:
        if images or attachments:
            return {"ok": False, "error": "Codex terminal does not support attachments yet"}
        if not self._process or self._process.poll() is not None:
            return {"ok": False, "error": "process not running"}
        if self._stdin_closed:
            return {"ok": False, "error": "Codex terminal accepts one prompt per process"}

        with self._stdin_lock:
            try:
                if not self._process.stdin:
                    return {"ok": False, "error": "process stdin unavailable"}
                self._process.stdin.write(text)
                self._process.stdin.write("\n")
                self._process.stdin.close()
                self._stdin_closed = True
            except (BrokenPipeError, OSError) as exc:
                self._status = "stopped"
                return {"ok": False, "error": str(exc)}

        self._awaiting_response = True
        return {"ok": True, "error": ""}

    def send_permission_response(
        self,
        request_id: str,
        decision: str,
        session_id: str | None = None,
    ) -> dict:
        return {"ok": False, "error": "Codex terminal does not support permission prompts yet"}

    def interrupt(self) -> dict:
        if not self._process or self._process.poll() is not None:
            return {"ok": False, "error": "process not running"}
        try:
            os.kill(self._process.pid, signal.SIGINT)
        except OSError as exc:
            return {"ok": False, "error": str(exc)}
        self._awaiting_response = False
        return {"ok": True, "error": ""}

    def kill(self) -> dict:
        if not self._process:
            self._status = "stopped"
            return {"ok": True, "error": ""}
        if self._process.poll() is not None:
            self._status = "stopped"
            self._process = None
            return {"ok": True, "error": ""}
        try:
            self._process.terminate()
            try:
                self._process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=5)
        except OSError as exc:
            return {"ok": False, "error": str(exc)}
        finally:
            self._status = "stopped"
            self._awaiting_response = False
            self._process = None
        return {"ok": True, "error": ""}

    def get_in_flight_snapshot(self) -> dict | None:
        return None

    def set_external_status(self, status: str) -> None:
        self._status = status

    def set_session_id(self, session_id: str) -> None:
        self._session_id = session_id
        self._persist_session_id()

    def set_persist_file(self, persist_file: str | None) -> None:
        self._persist_file = persist_file

    def _persist_session_id(self) -> None:
        if not self._persist_file or not self._session_id:
            return
        try:
            Path(self._persist_file).write_text(self._session_id, encoding="utf-8")
        except OSError as exc:
            logger.debug("codex session id persist failed: %s", exc)

    def _read_stdout_loop(self) -> None:
        proc = self._process
        if not proc or not proc.stdout:
            return
        output_parts: list[str] = []
        try:
            for line in proc.stdout:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    data = json.loads(stripped)
                    if not isinstance(data, dict):
                        data = {"type": "stdout", "text": str(data)}
                except json.JSONDecodeError:
                    data = {"type": "stdout", "text": stripped}

                text = _event_text(data)
                if text:
                    output_parts.append(text)
                    self._channel.broadcast({
                        "type": "stream_event",
                        "session_id": self._session_id,
                        "event": {
                            "type": "content_block_delta",
                            "delta": {"type": "text_delta", "text": text},
                        },
                        "raw": data,
                    })
        except (ValueError, OSError):
            pass
        finally:
            try:
                proc.wait(timeout=5)
            except (subprocess.TimeoutExpired, OSError):
                pass

            exit_code = proc.returncode
            self._awaiting_response = False
            self._status = "idle" if exit_code == 0 else "stopped"
            result_text = "".join(output_parts)
            server_debug_log("codex_process_exit", {
                "exit_code": exit_code,
                "session_id": self._session_id,
            })
            self._channel.broadcast({
                "type": "result",
                "subtype": "success" if exit_code == 0 else "error",
                "is_error": exit_code != 0,
                "result": result_text,
                "duration_ms": 0,
                "session_id": self._session_id,
                "total_cost_usd": 0,
                "usage": {},
            })
            self._channel.broadcast({
                "type": "system",
                "subtype": "process_exit",
                "exit_code": exit_code,
                "session_id": self._session_id,
            })
            if exit_code != 0:
                self._channel.broadcast({
                    "type": "error",
                    "message": f"Codex process exited with code {exit_code}",
                    "exit_code": exit_code,
                    "session_id": self._session_id,
                })
