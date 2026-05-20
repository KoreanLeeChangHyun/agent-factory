# Project Codex Assets

This directory is the project-local counterpart to `.claude/` for Codex-facing
assets.

Keep only repository-safe Codex configuration, rules, and integration notes here.
Do not copy runtime state from `$HOME/.codex` into this directory. In particular,
keep auth files, logs, sqlite databases, history, sessions, shell snapshots, and
cache files under the user-level Codex home.

Current intent:

- `.codex/rules/` holds project-specific Codex rules.
- `.codex/skills/` holds project-specific Codex skills.
- Agent Factory runtime integration remains under `.agent-factory/`.
- Claude Code assets remain under `.claude/`.

Project skills:

- `agent-factory-workflow`: overall repository boundaries and workflow.
- `agent-factory-workrequest-ouroboros`: WorkRequest/ticket authoring loop.
- `agent-factory-cleanup`: source/runtime cleanup and path moves.
- `agent-factory-adapter`: provider and external-system adapter changes.
- `agent-factory-board-runtime`: board API, frontend, SSE, and config paths.
- `agent-factory-hooks-guards`: hooks, guards, and permission schema work.
- `agent-factory-verification`: focused validation selection.
