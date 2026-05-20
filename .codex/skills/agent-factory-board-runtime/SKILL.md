---
name: agent-factory-board-runtime
description: Use when modifying Agent Factory board server, board API handlers, frontend workflow UI, SSE updates, memory/rules/prompt file APIs, or board runtime paths. Preserve API routes, event semantics, and source/runtime separation.
---

# Agent Factory Board Runtime

Use this skill for `.agent-factory/board` and board-facing app changes.

## Boundary Rules

- Board backend source belongs under `.agent-factory/board` and board API app modules.
- Board runtime data belongs under `.agent-factory/board/data` and is ignored.
- User-editable config belongs under `.agent-factory/board/config`.
- Frontend files should keep existing route and state names unless a migration updates every caller.

## Workflow

1. Search backend route, frontend fetch, and tests before changing an endpoint or file path.
2. Keep existing API URLs stable unless the user explicitly asks for a breaking change.
3. If moving data helpers, preserve compatibility exports until all imports are migrated.
4. For SSE changes, verify event type, payload shape, frontend listener, and watcher trigger together.
5. Run focused board tests under `.agent-factory/tests/contracts/board_api` for API changes.

## Common Checks

- `rg -n "/api/path|event_name|helper_name" .agent-factory/board .agent-factory/tests`
- `python3 -m py_compile` for changed Python board modules.
- Board UI text should name current paths if a path appears in the interface.

