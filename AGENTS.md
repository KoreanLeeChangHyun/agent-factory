# AGENTS.md

This repository is an Agent Factory workspace. Treat `.agent-factory/` as the
runtime source tree for the local workflow engine, board UI, hooks, guards, and
tests.

## Repository Boundaries

- Keep Agent Factory source code under `.agent-factory/engine`,
  `.agent-factory/board`, and `.agent-factory/tests`.
- Keep project-local Codex assets under `.codex/`.
- Keep Claude Code assets under `.claude/`.
- Keep external reference repositories under `repo/`; do not import from them
  directly.
- Keep temporary local artifacts under `temp/`; do not depend on them in source
  code.

## Working Rules

- Prefer existing Agent Factory patterns over new abstractions.
- Keep external systems behind adapters.
- Preserve source/runtime separation; runtime state belongs in
  `.agent-factory/runs`, `.agent-factory/logs`, `.agent-factory/worktrees`, or
  local cache directories.
- Before moving or deleting files, search references and update affected paths.
- For board changes, preserve API routes, SSE event semantics, and static asset
  paths.
- For hooks and guards, keep JSON schemas and guard messages stable unless the
  task explicitly changes them.

## Verification

- Use focused validation for the touched boundary.
- For board frontend JavaScript, run `node --check` on changed files.
- For board API/runtime changes, run focused tests from `.agent-factory/tests`.
- Report exactly what was verified and what was not.
