"""Claude CLI implementation of the LLMAdapter contract."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from engine.core.ports.llm import EventHandler, LLMEvent, LLMRequest, LLMResult
from engine.core.workflows import stage_to_v2_step
from engine.v2._spawn import DEFAULT_PERMISSION_MODE, spawn_claude


def _step_name(request: LLMRequest) -> str:
    if request.step:
        return request.step
    if request.stage is not None:
        return stage_to_v2_step(request.stage)
    return ""


@dataclass(frozen=True)
class ClaudeAdapter:
    """Adapter that preserves the existing `claude -p` subprocess behavior."""

    permission_mode: str = DEFAULT_PERMISSION_MODE
    add_dirs: tuple[Path, ...] = ()

    def complete(
        self,
        request: LLMRequest,
        *,
        on_event: EventHandler | None = None,
    ) -> LLMResult:
        events: list[LLMEvent] = []

        def _on_line(raw: dict) -> None:
            text = ""
            if raw.get("type") == "assistant":
                msg = raw.get("message") or {}
                for block in msg.get("content") or []:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text += str(block.get("text", ""))
            event = LLMEvent(type=str(raw.get("type") or ""), text=text, raw=raw)
            events.append(event)
            if on_event is not None:
                on_event(event)

        result = spawn_claude(
            prompt_body=request.prompt,
            session_id=request.session_id,
            system_prompt=request.system_prompt,
            cwd=request.cwd or Path.cwd(),
            step=_step_name(request),
            resume=request.resume,
            timeout=request.timeout,
            permission_mode=self.permission_mode,
            add_dirs=self.add_dirs,
            on_line=_on_line,
        )
        return LLMResult(
            ok=result.returncode == 0 and not result.timed_out,
            output_text=result.stdout,
            error=result.stderr,
            timed_out=result.timed_out,
            returncode=result.returncode,
            session_id=request.session_id,
            terminal_reason=result.terminal_reason,
            events=events,
        )
