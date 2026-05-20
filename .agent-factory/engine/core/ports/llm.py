"""Provider-independent LLM adapter contract."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol

from engine.core.workflows import WorkflowStage


@dataclass(frozen=True)
class LLMEvent:
    """Normalized event emitted while an LLM request is running."""

    type: str
    text: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LLMRequest:
    """Provider-neutral request passed to an LLM adapter."""

    prompt: str
    system_prompt: str = ""
    session_id: str = ""
    cwd: Path | None = None
    stage: WorkflowStage | None = None
    step: str = ""
    resume: bool = False
    timeout: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LLMResult:
    """Provider-neutral LLM execution result."""

    ok: bool
    output_text: str = ""
    error: str = ""
    timed_out: bool = False
    returncode: int = 0
    session_id: str = ""
    terminal_reason: str = ""
    events: list[LLMEvent] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


EventHandler = Callable[[LLMEvent], None]


class LLMAdapter(Protocol):
    """Boundary for model/runtime providers."""

    def complete(
        self,
        request: LLMRequest,
        *,
        on_event: EventHandler | None = None,
    ) -> LLMResult:
        """Run one LLM request."""


@dataclass
class FakeAdapter:
    """Deterministic adapter for application tests."""

    results: list[LLMResult] = field(default_factory=list)
    default_result: LLMResult = field(default_factory=lambda: LLMResult(ok=True))
    requests: list[LLMRequest] = field(default_factory=list)

    def complete(
        self,
        request: LLMRequest,
        *,
        on_event: EventHandler | None = None,
    ) -> LLMResult:
        self.requests.append(request)
        result = self.results.pop(0) if self.results else self.default_result
        for event in result.events:
            if on_event is not None:
                on_event(event)
        return result
