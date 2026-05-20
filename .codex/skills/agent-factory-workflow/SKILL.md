---
name: agent-factory-workflow
description: Use when working on this repository's Agent Factory runtime, including .agent-factory engine, board, hooks, guards, workflow orchestration, provider adapters, or project-local .codex/.claude integration. Follow existing boundaries and avoid mixing runtime state with source assets.
---

# Agent Factory Workflow

Use this skill for changes inside this repository's Agent Factory system.

## Boundaries

- Runtime source lives under `.agent-factory/engine`, `.agent-factory/board`, `.agent-factory/hooks`, and `.agent-factory/bin`.
- Claude Code project assets live under `.claude/`.
- Codex project assets live under `.codex/`.
- Runtime state and local outputs live under `.agent-factory/runs`, `.agent-factory/logs`, `.agent-factory/worktrees`, `.agent-factory/staging`, and cache directories. Do not treat those as source.
- Provider-specific names belong in adapter or integration surfaces. Keep core/application code provider-neutral where practical.

## Workflow

1. Inspect existing imports and tests before moving files.
2. Preserve compatibility wrappers when callers still import old paths.
3. Keep edits scoped to the requested cleanup or feature.
4. Do not copy user-level `$HOME/.codex` runtime files into the project.
5. Validate with focused tests for the touched boundary when code behavior changes.

For WorkRequest or ticket authoring, use `agent-factory-workrequest-ouroboros`
before accepting the request for execution.

## Common Checks

- Use `rg` for references before deleting or moving a path.
- Use `python3 -m py_compile` for changed Python modules when tests are too broad.
- For hook or guard changes, run the focused hook tests under `.agent-factory/tests/adapters/hooks`.
- For board API changes, run focused tests under `.agent-factory/tests/contracts/board_api`.
