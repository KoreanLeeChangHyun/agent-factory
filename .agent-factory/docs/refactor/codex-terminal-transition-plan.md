# Codex Terminal Transition Plan

## Status

Planned.

Current state:

- `CodexAdapter` exists under `engine/adapters/llm`.
- `AGENT_FACTORY_LLM_PROVIDER=codex` selects Codex for provider-neutral
  `LLMAdapter` paths.
- Board Settings can expose and save the active brain provider.
- `BrainProcess` exists as the provider-neutral board terminal process
  contract, with `ClaudeBrainProcess` wrapping the current `ClaudeProcess`.
- The interactive Terminal surface still runs through `ClaudeProcess`.

This means Codex can be selected for adapter-backed workflow paths, and the
live Console terminal has a provider-neutral process boundary. It is not yet a
Codex terminal.

## Goal

Make the Agent Factory Console terminal provider-neutral while preserving the
existing Claude terminal behavior.

Target provider shape:

```text
BrainProcess
  -> ClaudeProcess
  -> CodexProcess
```

## Non-Goals

- Do not remove Claude support.
- Do not change the public terminal routes until compatibility tests exist.
- Do not expose Gemini as a runnable terminal provider until a real
  `GeminiAdapter` and process implementation exist.

## Plan

### 1. Freeze Current Provider Semantics

- Keep `AGENT_FACTORY_LLM_PROVIDER` as the source of truth for adapter-backed
  LLM paths.
- In Settings, label the terminal capability separately from the selected
  provider.
- Show a clear state such as `Terminal: Claude only` or `Terminal: Codex
  experimental`.

### 2. Extract A BrainProcess Contract

Introduce a provider-neutral process interface around the methods already used
by terminal routes:

- `spawn(extra_args)`
- `send_input(text, attachments)`
- `kill()`
- `interrupt()`
- `status`
- `session_id`
- `get_in_flight_snapshot()`

The first implementation should wrap the current `ClaudeProcess` without
behavior changes.

### 3. Add CodexProcess

Implement a minimal Codex terminal process using Codex CLI.

Expected command foundation:

```text
codex exec --json -
```

Responsibilities:

- start a Codex subprocess
- stream stdout JSON lines
- normalize Codex events into the existing terminal SSE event model
- preserve stderr and process exit metadata
- reject unsupported Claude-only commands with a clear terminal event

### 4. Route Terminal Endpoints Through The Active Process

Update terminal routes to resolve the active process from provider settings:

- `/terminal/start`
- `/terminal/input`
- `/terminal/status`
- `/terminal/command`
- `/terminal/interrupt`
- `/terminal/stop`

Provider changes should apply to the next terminal session unless an explicit
restart is requested.

### 5. Define Provider Capabilities

Add a small capability object per provider.

Examples:

- supports login command
- supports resume
- supports interrupt
- supports attachments
- supports JSON event streaming

This prevents Claude-specific actions like `/login` from being shown as
universal behavior.

### 6. Update UI

- Show active provider in the terminal status surface.
- Show terminal capability next to the Brain provider setting.
- Keep color theme tied to the selected brain.
- Keep unsupported provider controls disabled with concise labels.

### 7. Verification

Required tests:

- `ClaudeProcess` wrapper preserves existing terminal behavior.
- `CodexProcess` maps JSON stdout events into terminal SSE events.
- provider setting chooses the expected process factory.
- terminal routes keep Claude behavior by default.
- Codex terminal smoke test covers spawn, input, status, and stop.

Manual verification:

- start Agent Factory Console
- select Codex in Settings
- restart terminal session
- send a small prompt
- confirm streamed output renders in Terminal
- switch back to Claude and confirm existing flow still works

## Risks

- Codex CLI event schema may differ across versions.
- Codex interactive semantics may not match Claude session semantics.
- Existing terminal UI assumes Claude-specific session metadata.
- `/login`, resume, attachment, and permission flows are not guaranteed to map
  one-to-one across providers.

## Recommended Implementation Order

1. Add `BrainProcess` contract and `ClaudeBrainProcess` wrapper. (done)
2. Move route usage from direct `ClaudeProcess` access to the process factory.
3. Add `CodexProcess` with stdout normalization only.
4. Add provider capability reporting.
5. Update Settings and Terminal UI capability labels.
6. Add route-level and adapter-level tests.
