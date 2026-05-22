# Action Render Event

## Purpose

`ActionRenderEvent` is the provider-neutral event contract used by the Desk.
The Desk should render what happened in the work request and workflow, not the
raw Claude, Codex, or Gemini tool protocol.

Every user-visible operation is treated as an action:

- a user asks for work
- an agent asks a clarification question
- a work request field changes
- a workflow stage starts or completes
- a file is read or changed
- a shell command runs
- a web search or fetch happens
- an approval is requested or resolved
- usage, errors, and verification results are recorded

Provider-specific names belong in adapters. Desk rendering depends on
`ActionRenderEvent.action.kind`.

## Event Shape

Initial JSON shape:

```json
{
  "type": "action.render",
  "schema": "agent-factory.action-render-event.v1",
  "id": "evt-001",
  "timestamp": "2026-05-22T12:00:00Z",
  "actor": {
    "kind": "agent",
    "provider": "codex",
    "name": "Codex"
  },
  "action": {
    "kind": "file.change",
    "category": "filesystem",
    "status": "completed",
    "confidence": "direct",
    "label": "File changed",
    "target": ".agent-factory/engine/adapters/llm/codex.py"
  },
  "surface": {
    "kind": "desk",
    "zone": "request"
  },
  "work_request": {
    "id": "WR-123",
    "status": "draft"
  },
  "workflow": {
    "id": "WF-WR-123-20260522-120000",
    "stage": "PLAN"
  },
  "provider_tool": {
    "provider": "codex",
    "name": "file_changes"
  },
  "summary": "Updated Codex adapter event parsing.",
  "details": "",
  "payload": {},
  "raw": {}
}
```

Only `type`, `schema`, `id`, `timestamp`, `actor`, `action`, and `summary`
are required for v1. Other fields are optional and should be included when the
adapter can supply them without inventing precision.

## Confidence

Adapters must declare how reliable the mapping is.

```text
direct
  The provider emitted a tool or event that maps clearly to this action.

inferred
  The adapter inferred the action from a broader event, text, stat, or diff.

summary
  The action was generated after completion from aggregate run statistics.
```

This is required because provider event detail is uneven:

- Claude Code exposes precise tool hooks.
- Codex emits JSONL item events with typed items.
- Gemini headless JSON exposes tool statistics and file modification
  statistics, but not always a full step-by-step event stream.

## ActionKind v1

Desk-facing action kinds:

```text
message.emit
reasoning.emit

question.ask
question.answer

work_request.create
work_request.update
work_request.move
work_request.accept
work_request.complete

workflow.start
workflow.stage.start
workflow.stage.progress
workflow.stage.complete
workflow.complete
workflow.fail

plan.update

file.read
file.list
file.search
file.write
file.edit
file.change
file.delete

bash.run
bash.output
bash.complete
bash.fail

web.search
web.fetch

mcp.call

approval.request
approval.resolve

agent.spawn

usage.record
error.raise
```

### Filesystem Notes

Use `file.write` for create-or-overwrite operations. Claude Code uses `Write`
and Gemini CLI uses `write_file`; both names include overwrite behavior.

Use `file.change` when the provider only reports a broad file change. Codex
documents `file changes` as a JSONL item category, so adapters must not assume
they can always split changes into create, edit, and delete.

Use `file.delete` only when deletion is known. If deletion is observed through
a shell command, emit both:

- `bash.run` / `bash.complete` for the command
- `file.delete` with `confidence: "inferred"` when the target is clear

## Provider Event Sources

### Claude Code

Primary source: hooks.

Official Claude Code hooks expose:

- `PreToolUse`
- `PostToolUse`
- `PostToolUseFailure`
- `PermissionRequest`
- `PermissionDenied`

Tool events include `tool_name`, `tool_input`, and `tool_use_id`. Common
matchers include:

```text
Bash
Edit
Write
Read
Glob
Grep
Agent
WebFetch
WebSearch
AskUserQuestion
ExitPlanMode
mcp__<server>__<tool>
```

Useful mappings:

```text
Bash            -> bash.run / bash.output / bash.complete / bash.fail
Read            -> file.read
Glob            -> file.list
Grep            -> file.search
Write           -> file.write
Edit            -> file.edit
WebSearch       -> web.search
WebFetch        -> web.fetch
Agent           -> agent.spawn
AskUserQuestion -> question.ask
mcp__*          -> mcp.call
Permission*     -> approval.request / approval.resolve
```

Claude mappings are usually `confidence: "direct"`.

### Codex CLI

Primary source: `codex exec --json`.

Official Codex non-interactive mode says JSONL output includes event types:

```text
thread.started
turn.started
turn.completed
turn.failed
item.*
error
```

The documented item categories include:

```text
agent messages
reasoning
command executions
file changes
MCP tool calls
web searches
plan updates
```

Useful mappings:

```text
thread.started             -> workflow.start or provider metadata
turn.started               -> workflow.stage.start or status
turn.completed.usage       -> usage.record
turn.failed                -> workflow.fail / error.raise
item: agent_message        -> message.emit
item: reasoning            -> reasoning.emit
item: command_execution    -> bash.run / bash.complete / bash.fail
item: file_changes         -> file.change
item: mcp tool call        -> mcp.call
item: web search           -> web.search
item: plan update          -> plan.update
error                      -> error.raise
```

Codex should preserve the provider thread id as provider metadata. Current
Codex JSONL may place assistant text in nested `item.text`, so adapters must
parse both top-level text fields and nested item text.

### Gemini CLI

Primary source: headless mode with `--output-format json`, plus tool-specific
documentation.

Gemini headless JSON provides:

```text
response
stats.models
stats.tools.totalCalls
stats.tools.totalSuccess
stats.tools.totalFail
stats.tools.totalDurationMs
stats.tools.totalDecisions
stats.tools.byName
stats.files.totalLinesAdded
stats.files.totalLinesRemoved
error
```

Gemini CLI tool docs define:

```text
list_directory
read_file
write_file
glob
search_file_content
run_shell_command
web_fetch
google_web_search
read_many_files
save_memory
MCP servers
```

Useful mappings:

```text
response                         -> message.emit
stats.tools.byName.read_file     -> file.read
stats.tools.byName.list_directory-> file.list
stats.tools.byName.glob          -> file.list
stats.tools.byName.search_file_content -> file.search
stats.tools.byName.write_file    -> file.write or file.change
stats.tools.byName.edit          -> file.edit or file.change
stats.tools.byName.run_shell_command -> bash.run / bash.complete
stats.tools.byName.web_fetch     -> web.fetch
stats.tools.byName.google_web_search -> web.search
stats.files totals               -> file.change
error                            -> error.raise
```

Gemini mappings from aggregate stats should use `confidence: "summary"` unless
the adapter is consuming a more detailed event stream.

## Adapter Rules

Adapters must:

1. Preserve raw provider events in `raw` when practical.
2. Put provider-specific tool names in `provider_tool.name`.
3. Emit provider-neutral behavior in `action.kind`.
4. Use `confidence` instead of inventing detail.
5. Keep Desk code provider-agnostic.
6. Keep Console raw stream rendering separate from Desk action rendering.

Adapters must not:

1. Expose Claude, Codex, or Gemini raw tool names as Desk rendering keys.
2. Treat provider permission models as identical.
3. Split broad events into precise actions unless the evidence is present.
4. Require Desk UI code to parse provider JSON.

## Desk Surfaces

The current Desk has two primary zones:

```text
request
  The user-agent space for creating and refining a WorkRequest.

conveyor
  The workflow observation space for Draft -> Accepted -> Executing ->
  Verifying -> Complete.
```

`surface.zone` should be one of:

```text
request
conveyor
workflow
artifact
verification
```

The same action may render differently by zone. For example:

- `question.ask` in `request` renders as a clarification prompt.
- `workflow.stage.complete` in `conveyor` updates a card or stage marker.
- `file.change` in `artifact` renders as a changed-file row.

## References

- Claude Code tools reference:
  https://code.claude.com/docs/en/tools-reference
- Claude Code hooks reference:
  https://code.claude.com/docs/en/hooks
- Codex non-interactive mode:
  https://developers.openai.com/codex/noninteractive
- Codex permissions:
  https://developers.openai.com/codex/permissions
- Gemini CLI tools:
  https://google-gemini.github.io/gemini-cli/docs/tools/
- Gemini CLI file system tools:
  https://google-gemini.github.io/gemini-cli/docs/tools/file-system.html
- Gemini CLI shell tool:
  https://google-gemini.github.io/gemini-cli/docs/tools/shell.html
- Gemini CLI web fetch:
  https://google-gemini.github.io/gemini-cli/docs/tools/web-fetch.html
- Gemini CLI web search:
  https://google-gemini.github.io/gemini-cli/docs/tools/web-search.html
- Gemini CLI headless mode:
  https://google-gemini.github.io/gemini-cli/docs/cli/headless.html
