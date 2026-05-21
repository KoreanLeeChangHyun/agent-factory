"""Production-line spawn — claude -p subprocess wrapper.

SPEC.md §8 — 1 subprocess per step. cwd=work_dir, --append-system-prompt,
--session-id, --resume <session_id> Retry support.

T-495 Phase 2 (driver) — Replaced with `--output-format stream-json --verbose` +
subprocess.run → Popen + readline loop + line callback. driver is NDJSON
Each line is forwarded to an endpoint for each meaning.

Regression fix (4 regressions reviewed in Phase 2-A):
- session_id is a required UUID according to the claude CLI `--session-id <uuid>` protocol.
- logical_name (`wf-T489-PLAN`) is separated for debug/log quoting purposes.
- Specify --permission-mode (avoid non-interactive `-p` mode permission blocking)
- Allow work_dir tool access with --add-dir (cwd reinforcement)
"""

from __future__ import annotations

import json
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from ._common import STEP_TIMEOUT_BY_STEP


CLAUDE_BIN = "claude"
DEFAULT_PERMISSION_MODE = "bypassPermissions"


@dataclass
class SpawnResult:
    """claude -p subprocess result.

    Attributes:
        returncode: process returncode (-1 on timeout)
        stdout: assistant message.content[].text accumulated (for compatibility — verify reads artifact file)
        stderr: stderr all
        timed_out: Whether deadline is exceeded
        ndjson_lines: List of parsed NDJSON line dict (for testing + diagnosis)
        terminal_reason: result.terminal_reason ("completed", etc.). If not, an empty string
    """

    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False
    ndjson_lines: list[dict[str, Any]] = field(default_factory=list)
    terminal_reason: str = ""


def new_session_uuid() -> str:
    """UUID4 for claude `--session-id <uuid>` — Generate 1 per new session."""
    return str(uuid.uuid4())


def logical_session_name(work_request_no: str, step: str, phase_id: str | None = None) -> str:
    """Logical name for debug/log quoting. Not passed to claude.

    Example: "wf-WR489-PLAN", "wf-WR489-WORK-P1". Used as key of ctx.session_ids.
    """
    base = f"wf-{work_request_no.replace('-', '')}-{step}"
    if phase_id is not None:
        return f"{base}-{phase_id}"
    return base


def _extract_assistant_text(obj: dict[str, Any]) -> str:
    """Join only the text block in the assistant NDJSON line.

    shape (claude -p stream-json ground truth):
        {"type":"assistant","message":{"content":[{"type":"text","text":"..."}]}}
    """
    if obj.get("type") != "assistant":
        return ""
    msg = obj.get("message") or {}
    content = msg.get("content") or []
    pieces: list[str] = []
    for blk in content:
        if isinstance(blk, dict) and blk.get("type") == "text":
            pieces.append(str(blk.get("text", "")))
    return "".join(pieces)


def spawn_claude(
    *,
    prompt_body: str,
    session_id: str,
    system_prompt: str,
    cwd: Path,
    step: str,
    resume: bool = False,
    timeout: int | None = None,
    permission_mode: str = DEFAULT_PERMISSION_MODE,
    add_dirs: tuple[Path, ...] = (),
    on_line: Callable[[dict[str, Any]], None] | None = None,
) -> SpawnResult:
    """claude -p subprocess fire (stream-json mode).

    - Specify output creation location with cwd=work_dir (SPEC.md §8.4)
    - --output-format stream-json --verbose (T-495 P1)
    - Inject system prompt for each step with --append-system-prompt (10KB or less)
    - --session-id <uuid> or --resume <uuid>
    - Specify --permission-mode <mode> (default: bypassPermissions)
    - Add a directory that allows tool access with --add-dir <path>
    - prompt_body is passed to stdin
    - on_line(obj) callback — Called every NDJSON line (skip if None)
      Callback exceptions are absorbed silently — driver flow impact 0
    """
    effective_timeout = timeout if timeout is not None else STEP_TIMEOUT_BY_STEP.get(step, 600)
    cmd = [CLAUDE_BIN, "-p", "--output-format", "stream-json", "--verbose"]
    if resume:
        cmd += ["--resume", session_id]
    else:
        cmd += ["--session-id", session_id]
    if system_prompt:
        cmd += ["--append-system-prompt", system_prompt]
    cmd += ["--permission-mode", permission_mode]
    for d in (cwd, *add_dirs):
        cmd += ["--add-dir", str(d)]

    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(cwd),
            text=True,
            bufsize=1,  # line-buffered
        )
    except (FileNotFoundError, OSError) as exc:
        return SpawnResult(
            returncode=-1,
            stdout="",
            stderr=f"spawn failed: {exc}",
            timed_out=False,
        )

    # Pass prompt to stdin + close (claude reads EOF and starts exit flow)
    try:
        if proc.stdin is not None:
            proc.stdin.write(prompt_body)
            proc.stdin.close()
    except (BrokenPipeError, OSError):
        pass

    text_buf: list[str] = []
    ndjson_lines: list[dict[str, Any]] = []
    terminal_reason = ""
    timed_out = False

    deadline = time.monotonic() + effective_timeout

    assert proc.stdout is not None
    try:
        for raw_line in proc.stdout:
            if time.monotonic() > deadline:
                timed_out = True
                break
            line = raw_line.rstrip("\n")
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                # Ignore noise lines other than stream-json (may occur in test mode)
                continue
            if not isinstance(obj, dict):
                continue
            ndjson_lines.append(obj)
            text_chunk = _extract_assistant_text(obj)
            if text_chunk:
                text_buf.append(text_chunk)
            if obj.get("type") == "result":
                tr = obj.get("terminal_reason")
                if isinstance(tr, str):
                    terminal_reason = tr
            if on_line is not None:
                try:
                    on_line(obj)
                except Exception:
                    pass  # silent — driver flow impact 0
    except (OSError, ValueError):
        pass

    # Regression ③ Blocking — Completion processing after the readline loop ends.
    # If EOF is normal, wait() immediately secures the return code. If timeout, kill.
    if timed_out:
        try:
            proc.kill()
        except OSError:
            pass
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass
        returncode = -1
    else:
        try:
            returncode = proc.wait(timeout=max(0.1, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            try:
                proc.kill()
                proc.wait(timeout=2)
            except (subprocess.TimeoutExpired, OSError):
                pass
            timed_out = True
            returncode = -1

    try:
        stderr_text = proc.stderr.read() if proc.stderr is not None else ""
    except (OSError, ValueError):
        stderr_text = ""
    try:
        if proc.stdout is not None:
            proc.stdout.close()
        if proc.stderr is not None:
            proc.stderr.close()
    except OSError:
        pass

    stdout_text = "".join(text_buf)
    return SpawnResult(
        returncode=returncode,
        stdout=stdout_text,
        stderr=stderr_text or "",
        timed_out=timed_out,
        ndjson_lines=ndjson_lines,
        terminal_reason=terminal_reason,
    )


def spawn_claude_resume(
    *,
    prompt_body: str,
    session_id: str,
    system_prompt: str,
    cwd: Path,
    step: str,
    timeout: int | None = None,
    permission_mode: str = DEFAULT_PERMISSION_MODE,
    add_dirs: tuple[Path, ...] = (),
    on_line: Callable[[dict[str, Any]], None] | None = None,
) -> SpawnResult:
    """SPEC.md §6.3 — Continuing with the same session_id (UUID)."""
    return spawn_claude(
        prompt_body=prompt_body,
        session_id=session_id,
        system_prompt=system_prompt,
        cwd=cwd,
        step=step,
        resume=True,
        timeout=timeout,
        permission_mode=permission_mode,
        add_dirs=add_dirs,
        on_line=on_line,
    )
