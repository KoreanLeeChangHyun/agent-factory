# LLM Adapter Architecture

## Target

`.agent-factory` owns the workflow model and the orchestration runtime. Model
vendors and coding agents are plugins behind an adapter boundary.

```text
.agent-factory
  <-> LLMAdapter
      <-> ClaudeAdapter
      <-> CodexAdapter
      <-> GeminiAdapter
      <-> FakeAdapter
```

The core workflow must not know whether a step is executed by Claude, Codex,
Gemini, or a deterministic fake used for tests.

## Vocabulary

Use `LLMAdapter` as the boundary name.

Avoid `ClaudeRunner`, `spawn_claude`, or provider names in core/application
modules. Provider names belong only under adapter implementations and user-facing
configuration.

## Port Shape

Initial protocol:

```python
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True)
class LLMRequest:
    prompt: str
    system_prompt: str
    cwd: Path
    step: str
    session_id: str | None = None
    resume: bool = False
    timeout_seconds: int | None = None
    writable_roots: tuple[Path, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LLMEvent:
    type: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class LLMResult:
    returncode: int
    text: str
    stderr: str = ""
    timed_out: bool = False
    session_id: str | None = None
    events: tuple[LLMEvent, ...] = ()
    terminal_reason: str = ""


class LLMAdapter(Protocol):
    name: str

    def run(self, request: LLMRequest) -> LLMResult:
        ...
```

Streaming can be added without changing the core contract by either:

- passing an optional event sink to `run`, or
- returning collected `LLMEvent` values in `LLMResult`.

The current V2 behavior already collects stream-json lines, so the first
migration can preserve collected events and add live forwarding later.

## Provider Adapters

### ClaudeAdapter

Current source:

- `engine/v2/_spawn.py`

Target:

- `engine/adapters/llm/claude.py`

Responsibilities:

- execute `claude -p`
- map stream-json lines to `LLMEvent`
- manage Claude-compatible session IDs
- handle `--permission-mode`
- handle `--add-dir`

### CodexAdapter

Target:

- `engine/adapters/llm/codex.py`

Responsibilities:

- run Codex CLI/API in non-interactive mode
- map output to `LLMResult`
- expose session or conversation IDs if available
- obey the same artifact/write-root contract

The core should not assume Codex has the same streaming or session model as
Claude.

### GeminiAdapter

Target:

- `engine/adapters/llm/gemini.py`

Responsibilities:

- run Gemini CLI/API in non-interactive mode
- normalize output/events
- expose provider diagnostics in `LLMResult.metadata` if needed

The core should not assume Gemini supports tool permissions the same way Claude
does.

### FakeAdapter

Target:

- `engine/adapters/llm/fake.py`

Responsibilities:

- deterministic TDD execution
- write expected artifacts for plan/work/report tests
- simulate timeout and non-zero return codes

This adapter is mandatory before large refactors. It lets application tests
avoid real LLM calls.

## Configuration

Suggested `.agent-factory/.settings` keys:

```text
AGENT_FACTORY_LLM_PROVIDER=claude
AGENT_FACTORY_LLM_TIMEOUT_PLAN=300
AGENT_FACTORY_LLM_TIMEOUT_WORK=1800
AGENT_FACTORY_LLM_TIMEOUT_VALIDATE=180
AGENT_FACTORY_LLM_TIMEOUT_REPORT=600
```

Provider-specific keys stay namespaced:

```text
CLAUDE_BIN=claude
CLAUDE_PERMISSION_MODE=bypassPermissions
CODEX_BIN=codex
GEMINI_BIN=gemini
```

## Dependency Rule

Allowed:

```text
application service -> LLMAdapter protocol
ClaudeAdapter -> subprocess/filesystem/provider CLI
CodexAdapter -> subprocess/API/provider CLI
GeminiAdapter -> subprocess/API/provider CLI
```

Forbidden:

```text
domain -> LLMAdapter
application -> ClaudeAdapter
application -> subprocess
application -> provider-specific JSON shape
board handler -> provider CLI
```

## Migration Plan

### Phase L0: Preserve Behavior

- Add `LLMAdapter`, `LLMRequest`, `LLMResult`, `LLMEvent` types.
- Wrap existing `spawn_claude` with `ClaudeAdapter`.
- Keep `engine/v2/_spawn.py` as a compatibility shim only during the phase.
- Tests should still pass.

### Phase L1: Application Injection

- Change PLAN/WORK/REPORT services to receive an `LLMAdapter`.
- Use `FakeAdapter` in application tests.
- Keep CLI behavior defaulting to `ClaudeAdapter`.

### Phase L2: Provider Selection

- Add provider factory:

```python
def make_llm_adapter(settings: Settings) -> LLMAdapter: ...
```

- Select `claude`, `codex`, `gemini`, or `fake`.
- Fail fast on unknown provider.

### Phase L3: Provider Implementations

- Add `CodexAdapter`.
- Add `GeminiAdapter`.
- Add contract tests shared by all adapters where practical.

### Phase L4: Remove Claude Assumptions

- Rename `session_id` usage where it is provider-specific.
- Rename metrics/events that say `claude` unless they are adapter-specific.
- Keep Claude mentions only under `adapters/llm/claude.py`, `.claude/`
  integration files, and provider docs.
